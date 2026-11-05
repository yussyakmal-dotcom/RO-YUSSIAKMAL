# Rancangan Django Models — V1 Lean
**Status:** baseline implementasi untuk tim engineering. **Tidak memakai custom user model.**  
**Sumber:** [PRD](./PRD.md), [DDL](./DDL.md), [Decision Log](./DECISION-LOG.md).

> Implementasi awal ORM tersedia di [`backend/ro_core/models.py`](../backend/ro_core/models.py). Modul belum diuji dengan project Django dan migration; finalisasi berikutnya adalah scaffold dan `makemigrations`.

## Paket dan struktur aplikasi
```text
backend/
  config/               settings, urls, celery
  core/                 auth permissions, audit, utility
  catalog/              Odoo master cache + mapping/capacity/schedule
  orders/               StoreOrder, StoreOrderLine
  planning/             ProductionPlan, ProductionPlanLine, MaterialRequestLine
  packing/              PackingAllocation
  integrations/         OdooDocument, DocumentCounter, JSON-2 client
```
Gunakan **Django auth User + Group** (STORE, PRODUCTION, PACKING, ADMIN), bukan akun auth custom. User dengan Group ADMIN dapat mengakses keempat workspace; audit tetap merekam identitas pemanggil.

## Model field minimum
Peta field berikut adalah *model contract* untuk implementasi. ORM adalah sumber kebenaran; `python manage.py makemigrations` menghasilkan DDL riil.

| Django model | Field inti |
|---|---|
| `Warehouse` | `odoo_id: BigInteger(unique)`, `code: Char(unique)`, `name: Char`, `kind: choices`, `stock_location_odoo_id: BigInteger(null)`, `active: Bool` |
| `Product` | `odoo_id: BigInteger(unique)`, `sku`, `name`, `category`, `uom`, `bom_odoo_id`, `bom_output_qty: Decimal(null)`, `bom_components: JSONField(default=list)`, `synced_at` |
| `ProductionAssignment` | `product: OneToOne(Product)`, `kitchen: FK(Warehouse)`, `is_active: Boolean(default=True)`, `sort_order: PositiveInteger(default=0)`, `updated_at` |
| `Schedule` | `code: unique`, `name`, `production_label`, `sort_order`, `active` |
| `ProductCapacity` | `product: FK`, `schedule: FK`, `max_qty: Decimal`; unique pair |
| `MinStockRule` | `product: FK`, `warehouse: FK`, `min_qty: Decimal`; unique pair |
| `UserWarehouseAccess` | `user: FK(settings.AUTH_USER_MODEL)`, `warehouse: FK`; unique pair |
| `StoreOrder` | `store: FK(Warehouse)`, `kitchen: FK(Warehouse)`, `order_date: Date`, `delivery_date: Date`, `schedule: FK`, `status: DRAFT/KIRIM/NO_ORDER`, `auto_submitted: Bool`, `submitted_at`, `created_at`; unique by store,kitchen,date,slot |
| `StoreOrderLine` | `order: FK`, `product: FK`, `qty: Decimal`; unique pair |
| `ProductionPlan` | `kitchen: FK`, `production_date`, `delivery_date`, `schedule`, `status: DRAFT/READY/SENT/PARTIAL`; unique by kitchen,production_date,delivery_date,slot |
| `ProductionPlanLine` | `plan: FK`, `product: FK`, `qty_requested`, `qty_planned`, `qty_mo`, `batch_qty`, `capacity_qty`, `bom_snapshot: JSONField(default=dict)`; unique pair |
| `MaterialRequestLine` | `plan: FK`, `product: FK`, `gross_qty`, `stock_qty`, `minimum_qty`, `buffer_qty`; unique pair; `requested_qty` dihitung property |
| `PackingAllocation` | `delivery_date`, `schedule: FK`, `store: FK`, `product: FK`, `qty_requested`, `qty_allocated`; unique by date,slot,store,product |
| `DocumentCounter` | `warehouse: FK`, `issue_date`, `last_value(default=10000)`; unique by warehouse+date |
| `OdooDocument` | `kind`, `source_document(unique)`, `origin_key(unique)`, `odoo_model`, `odoo_id(null)`, `state`, `payload: JSONField`, `error`, `created_at` |
| `AuditLog` | `actor: FK(User, null)`, `entity`, `entity_id`, `action`, `changes: JSONField`, `created_at` |

### Catatan Django
- Semua quantity: `DecimalField(max_digits=18, decimal_places=4)` plus `MinValueValidator(0)`; `bom_output_qty` dan `batch_qty` harus >0.
- Pilih `PROTECT` untuk master yang sudah direferensikan transaksi. Gunakan `CASCADE` hanya untuk line dalam header (StoreOrder→Line, Plan→Line). Master tidak dihapus, cukup `active=False`.
- Tambahkan `UniqueConstraint` yang ada di DDL dan `CheckConstraint` paling penting: Qty nonnegative, `qty_mo<=capacity_qty`.
- Simpan tanggal operasional `DateField`, waktu pembuatan/submit `DateTimeField` aware; `TIME_ZONE = 'Asia/Jakarta'`, `USE_TZ=True`.
- `bom_components` JSON sederhana: `[{ "odoo_product_id": 123, "qty": "1.0", "uom": "kg" }]`. Jangan gunakan float untuk kalkulasi.
- Validasi bahwa `kitchen.kind` adalah KITCHEN/ PACKING (PAKET) dan `store.kind` STORE di service layer.
- Audit business events di service layer dalam transaksi yang sama; jangan pasang signal pada seluruh save otomatis.
- `OdooDocument.origin_key`: nilai deterministik (mis. `MO:<plan_line_id>`, `MATERIAL:<plan_id>:<sku_id>`), bukan random retry key. Kunci unik ini menghindari transaksi ganda lokal.
- Konsolidasi dari `StoreOrderLine` pada request `KIRIM` dapat dihitung melalui query tanpa membuat tabel relasi 1:1 setiap SKU. Bila ingin jejak detail, simpan snapshot `order_ids`/source pada `bom_snapshot` atau report query; jangan mengandalkan current mutable Draft.
- Data `stock_qty` pada material line adalah snapshot perhitungan, bukan stok resmi.
- Gunakan transaksi atomik + row locking untuk submit, finalisasi plan, dan counter; network I/O Odoo **di luar** transaction.atomic.
- Task Celery untuk 07.00 WIB, sinkronisasi Odoo, dan outbox worker. Kegagalan API jangan menghilangkan record lokal.
- Jangan membuat `OdooDocument` dengan source yang sama untuk banyak MO; setiap dokumen Odoo mendapatkan kode unik tersendiri. `origin_key` menyimpan hubungan konsolidasi.

## Service functions prioritas
```python
submit_order(order_id, actor, automatic=False)
# lock DRAFT -> remove zero lines -> KIRIM or NO_ORDER

consolidate_orders(kitchen_id, delivery_date, schedule_id)
# KIRIM only; snapshot qty_requested; preserve qty_planned if plan edited

revise_plan_line(line_id, qty_planned, actor)
# ceil batch, capacity hard limit; recalc material needs

review_materials(plan_id, buffer_by_product, actor)
# gross from bom snapshots; net of available kitchen stock per schedule

prepare_odoo_drafts(plan_id, actor)
# local outbox first; create MO and Stock Transfer Draft via worker

allocate_packing(delivery_date, schedule_id, quantities, actor)
# priority for Paket, no change to StoreOrder source
```

## Minimal tests yang harus ada
1. Draft toko: 0 dihapus saat submit, Qty 1 diterima, full-zero → No Order.
2. Auto-submit 07.00 H-2 bisa di-run ulang tanpa menggandakan submit.
3. BoM 100, plan 210 → MO 300; over-capacity ditolak.
4. Revisi plan tidak mengubah store order; perubahan menyebabkan recompute material.
5. Stok dapur tidak dikurangi dua kali di jadwal berbeda.
6. Concurrent source number per kode+hari unik; hari berikutnya kembali 10001.
7. Timeout kirim MO → UNKNOWN; retry hanya setelah rekonsiliasi.
8. Administrator boleh semua workspace dan audit actor tetap administrator.

## Yang sengaja belum dipaksakan
Jangan membangun generic workflow, approval flow, full event sourcing, inventory movement, atau scheduling shift. Status dan model dapat ditambah nanti via migration. Hal terbuka PRD/decision log (DO, Paket demand ke dapur, exact stock quantity) diselesaikan sebelum mengaktifkan fitur terkait.

## Template order manual — V1
`ProductionAssignment` sekaligus sumber daftar SKU untuk formulir per dapur. File Excel diunggah melalui Django Admin; impor hanya memperbarui penugasan dan status template lokal, tidak menulis ke Odoo. Formulir toko mengambil daftar melalui `GET /api/v1/order-templates/<kode_dapur>/` (read-only dan perlu login). Qty selalu milik `StoreOrderLine`, bukan `ProductionAssignment`. Lihat [panduan template](./TEMPLATE-PEMESANAN.md) dan migration `0002_order_template_flags.py`.
