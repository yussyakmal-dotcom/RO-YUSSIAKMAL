# Workspace Admin Produksi — Rekap Kebutuhan (Tahap 1)

**Status:** implementasi backend API read-only dan tampilan React, **belum ProductionPlan**, belum batch/kapasitas/material, dan belum Odoo write.

## Tujuan

Melihat **total permintaan yang benar-benar sudah dikirim** dari seluruh toko, per **tanggal pengiriman × dapur × jadwal kirim × SKU**. Administrator dapat menelusuri Qty dan nomor order asal untuk setiap SKU.

Contoh jika Risoles Mayo diminta 25 oleh Toko Bandara dan 40 oleh Toko Kedaton, baris rekap menjadi **65 pcs** dengan sumber masing-masing toko. Draft toko lain, No Order, dan toko yang belum pernah membuat pesanan **tidak ikut total**.

## Alur tampilan

Buka `http://localhost:900/produksi/` setelah memperbarui Docker. Login menggunakan akun superuser/ADMIN yang sudah ada, atau akun dengan Group **PRODUCTION**. Group STORE **tidak dapat mengakses rekap**, walaupun mengetahui URL API.

1. Pilih **tanggal pengiriman** (default tampilan H+2 WIB, dapat diubah).
2. Pilih **dapur/packing** dan **jadwal kirim**.
3. Tinjau jumlah toko yang Kirim, No Order, Draft, atau belum membuat pesanan. Ini status terpisah: **belum membuat pesanan bukan No Order**.
4. Tinjau total Qty per SKU. Klik satu baris untuk membuka rincian Qty dan nomor order per toko.
5. Gunakan pencarian SKU/nama dan **Muat Ulang** untuk mengambil pembaruan pesanan.

Semua tindakan di halaman ini hanya membaca database PostgreSQL middleware. Tidak membuat/mengubah `StoreOrder`, `ProductionPlan`, MO atau transfer Odoo.

## API

```http
GET /api/v1/production/demand/?delivery_date=2026-11-08&kitchen_code=JP&schedule_code=SUBUH
```

Memerlukan autentikasi Django Session dan role **PRODUCTION** / **ADMIN** / superuser. Contoh bentuk respons:

```json
{
  "delivery_date": "2026-11-08",
  "kitchen": {"code": "JP", "name": "Dapur Jajan Pasar"},
  "schedule": {"code": "SUBUH", "name": "Subuh"},
  "basis": "FINAL_KIRIM_ONLY",
  "production_date": null,
  "summary": {
    "stores_total": 7,
    "stores_sent": 2,
    "stores_no_order": 1,
    "stores_draft": 1,
    "stores_not_entered": 3,
    "sku_count": 1,
    "qty_total": "65"
  },
  "store_statuses": [],
  "items": [{
    "product_id": 123,
    "sku": "10005",
    "name": "Risoles Mayo",
    "qty_total": "65",
    "store_count": 2,
    "sources": [
      {"store_code": "T_BAN", "store_name": "Toko Bandara", "order_id": 5, "qty": "25", "auto_submitted": false},
      {"store_code": "T_KD", "store_name": "Toko Kedaton", "order_id": 6, "qty": "40", "auto_submitted": true}
    ]
  }]
}
```

Di atas hanya ilustrasi; angka dan ID tidak berasal dari database pengguna. Response aktual selalu menyertakan status setiap toko dan detail SKU berdasarkan data.

### Aturan integritas
- `KIRIM` saja yang dihitung, baik kirim manual maupun otomatis.
- Qty pesanan toko integer; jika menemukan data historis final yang negatif, nol, atau pecahan, API mengembalikan **409** dengan ID yang perlu diperiksa, bukan membulatkan atau diam-diam menghilangkan baris.
- Rekap tetap memuat SKU yang sudah berubah/nonaktif dalam template, sebab order yang sudah final tidak boleh berubah hanya karena template diubah.
- Ringkasan dihitung langsung dari `StoreOrder` dan `StoreOrderLine`; tidak membuat tabel rekap yang dapat menjadi tidak sinkron.
- Jumlah Qtу dikirim sebagai string untuk menjaga presisi; UI menampilkan pemisah ribuan.
- Status **NOT_ENTERED** terpisah dari **NO_ORDER**, sehingga ketidakhadiran order terlihat eksplisit.

## Batas dan keputusan yang belum selesai
- Rekap menggunakan **tanggal pengiriman/jadwal kirim**, bukan otomatis menetapkan **tanggal produksi**. Pemetaan administrasi tanggal produksi, termasuk produksi lintas tengah malam, belum disetujui. Field `production_date` pada rekap sengaja `null`.
- **Rencana produksi masih tahap berikutnya.** Mengubah Qty rencana, pembulatan batch, kapasitas, stok bahan, penetapan Operation Type, pembuatan MO Draft dan transfer tidak dilakukan pada API ini.
- Aturan **late Draft setelah cutoff H-2 07.00 WIB** dan backlog saat downtime masih terbuka; tidak diubah pada milestone ini.
- Nama SKU pada rekap mengikuti **master Odoo terkini** (bukan snapshot nama ketika order dibuat); Qty dan nomor order berasal dari order final dan tidak berubah.
- Group PRODUCTION sekarang diizinkan login ke `/produksi/`, tetapi **tidak mendapatkan izin API pesanan toko**.

## Pengujian Debian

```bash
cd ~/RO-YUSSIAKMAL
git pull origin main
docker compose up -d --build --force-recreate api
docker compose exec api python manage.py check
docker compose exec api python manage.py test ro_core.test_production_demand
```

Buka:
- **Admin Produksi:** `http://localhost:900/produksi/`
- **Admin Toko:** `http://localhost:900/toko/`
- **Django Admin:** `http://localhost:900/admin/`

Untuk pertama kali uji melalui superuser Django. Nanti buat akun Admin Produksi sendiri melalui Django Admin → Users → Groups `PRODUCTION`.

## Mengapa pesanan KIRIM tidak terlihat di rekap?

Rekap memakai **tiga filter yang harus persis cocok** dengan Store Order: `delivery_date`, `kitchen`, dan `schedule`. Tanggal default di frontend adalah H+2 **hari ini (WIB)**, bukan otomatis tanggal pesanan terakhir. Misalnya pesanan T_BAN sudah `KIRIM` untuk 7 November dengan jadwal Pagi, tetapi layar melihat 8 November Subuh, maka toko terlihat **Belum membuat pesanan** untuk lingkup yang sedang dipilih. Data lama tidak hilang.

Untuk menghindari tebak-tebakan, halaman `/produksi/` kini memiliki panel **Temukan Pesanan yang Sudah Kirim** yang memuat hingga 30 Store Order `KIRIM` terbaru lintas tanggal/dapur/jadwal. Tombol **Lihat rekap** pada baris pesanan menyesuaikan ketiga filter sekaligus dan menampilkan konsolidasi yang tepat. Panel otomatis terbuka jika rekap sedang tidak memiliki toko KIRIM.

API helper khusus Admin Produksi (hanya baca):
```http
GET /api/v1/production/recent-orders/
```
Memperlihatkan ID Order, nama/kode toko, dapur, tanggal dan jadwal kirim, jumlah SKU, total Qty, serta auto/manual submit. Data ini **tidak mengubah pesanan** dan tidak membuat MO. Hanya 30 pesanan terbaru yang ditampilkan; jika order lebih lama tidak masuk daftar, cari di Django Admin → Store orders.

Jika pesanan KIRIM tidak terlihat di daftar mana pun, periksa `Store orders` pada `/admin/` untuk memastikan status dan nilai tanggal/dapur/jadwal; pertimbangkan juga apakah container menggunakan database PostgreSQL yang sama. Hasil CI bukan bukti isi database tenant lokal.
