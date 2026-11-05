# Template Pemesanan per Dapur — RO Middleware V1
**Status:** implementasi fondasi backend + Django Admin; frontend Admin Toko React belum dibangun.

## Keputusan operasional
- **Daftar SKU yang dapat dipesan toko dikelola manual di middleware**, bukan diturunkan dari Product Category atau otomatis dari BoM Odoo.
- **Satu dapur = satu template SKU bersama untuk seluruh toko**, disusun oleh Administrator. Contoh: pilih *Dapur Pastry* → daftar SKU dari template Pastry otomatis tampil.
- Setiap SKU punya tepat satu penugasan dapur pada tabel `ProductionAssignment` (dapat dipindah manual sesuai SOP), atribut **Aktif/Nonaktif** dan **Urutan tampil**.
- **Product.active** tetap master Odoo; **ProductionAssignment.is_active** adalah visibilitas di template middleware. Produk di salah satu status nonaktif tidak tampil di formulir baru.
- Qty **tidak disimpan dalam template**. Qty adalah milik **pesanan per toko × dapur × tanggal kirim × jadwal**, dan default 0 saat formulir baru dibuka. Menonaktifkan item template tidak mengubah histori pesanan yang sudah dibuat.
- **Operation Type Odoo** (bukan kategori ataupun template) menentukan gudang/lokasi manufaktur pada saat membuat MO. ID Operation Type akan dipetakan secara eksplisit ke dapur saat integrasi MO.
- PAKET boleh masuk template Packing (PCK) sebagai SKU yang dipesan toko, dengan prioritas produksi/perakitan sesuai PRD.

## Bentuk formulir Admin Toko (React, tahap berikutnya)

Pilihan Dapur: Pastry · Tanggal Pengiriman · Jadwal Kirim

| SKU / ID | Nama dari Odoo | Qty (editable) |
|---|---|---:|
| 12300 | Almond Choco Croissant Size M | 0 |
| 12306 | Beef Croissant Size M | 0 |
| 12303 | Almond Croissant Size S | 0 |

Pengguna **hanya mengisi Qty** dengan keyboard (Tab/Enter), tanpa memilih SKU baris demi baris. Tampilkan SKU aktif saja, pencarian dan virtualisasi sesuai volume 50–700 SKU. Submit Draft→Kirim menghapus baris Qty 0, tetapi Qty ≥1 valid. Simpan detail asli per toko untuk konsolidasi dan audit.

## Cara kelola template sementara di Django Admin

1. Login sebagai administrator di **http://localhost:900/admin/**.
2. Pilih **RO Middleware → Production Assignments** dan klik **Download Format Excel**.
3. Siapkan file `.xlsx` dengan kolom:
   - `SKU` (**wajib**) = Internal Reference dari Odoo, mis. `12300`. Jika ada nol di awal, format kolom sebagai **Text**.
   - `NAMA` opsional untuk pemeriksaan visual; nama produk resmi tetap dari master Odoo.
   - `AKTIF` = `Aktif` / `Nonaktif` (kosong berarti Aktif).
   - `URUTAN` = angka urutan tampil (kosong berarti urutan baris Excel).
4. Klik **Upload Template Excel**, pilih dapur (mis. **Dapur Pastry**) dan file `.xlsx`.
5. Klik **Preview Excel**, periksa error serta jumlah item baru/berubah. Untuk impor, **pilih ulang file yang sama** dan klik **Impor ke Middleware**.
6. Daftar bisa dikelola manual satu SKU per baris pada halaman Production Assignments, termasuk pindah dapur, edit Aktif dan Urutan.

### Kebijakan impor yang aman
- Maksimal 5 MB dan 5.000 baris per file.
- Validasi setiap SKU harus ditemukan dan **unik** di master hasil sinkronisasi Odoo.
- Jika SKU sudah ditugaskan ke dapur lain, impor **ditolak**, bukan dipindahkan diam-diam. Perpindahan dapur dilakukan manual.
- Jika ada baris invalid/duplikat, **seluruh impor ditolak** (tidak ada data parsial).
- Upload ulang bersifat idempotent. Item dengan SKU yang sudah ada di dapur itu boleh diubah Aktif/Urutan.
- SKU lama yang **tidak ada dalam file baru tetap dipertahankan** (tidak otomatis dinonaktifkan). Untuk menyembunyikan SKU, unggah SKU tersebut dengan `Nonaktif` atau edit via Admin.
- Tidak ada write ke Odoo, tidak mengubah Product/BoM, dan tidak menentukan Operation Type MO.
- Import dan edit admin dicatat di AuditLog secara sederhana.

## API read-only untuk frontend
```http
GET /api/v1/order-templates/PST/
```
Memerlukan login/autentikasi middleware. Contoh respons:
```json
{
  "kitchen": {"id": 1, "code": "PST", "name": "Dapur Pastry"},
  "count": 2,
  "items": [
    {"id": 10, "sku": "12300", "name": "Almond Choco Croissant Size M", "qty": 0},
    {"id": 11, "sku": "12306", "name": "Beef Croissant Size M", "qty": 0}
  ]
}
```

API hanya mengembalikan assignment aktif dengan Product.active dari Odoo juga aktif, diurutkan menggunakan `sort_order` dan nama. **Belum menyimpan Qty**; endpoint Draft/Kirim dan UI React dibuat pada langkah berikutnya.

## Basis data
Tidak ada tabel header template terpisah. **`ProductionAssignment` menjadi sumber template SKU per dapur**, dengan migration:
`ro_core/migrations/0002_order_template_flags.py`
- `is_active BOOLEAN NOT NULL DEFAULT TRUE`
- `sort_order INTEGER NOT NULL DEFAULT 0`

Pilihan ini mencegah penggandaan master SKU, mudah dipelihara, dan tetap mengikuti keputusan hanya satu dapur aktif per SKU. Jika kelak setiap toko memerlukan katalog berbeda, desain dapat diperluas saat ada kebutuhan nyata.
