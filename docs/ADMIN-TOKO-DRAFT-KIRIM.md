# Admin Toko — Draft dan Kirim Pesanan (Backend V1)
**Status:** API Django sudah diimplementasikan; frontend React SAP Fiori dan tugas otomatis 07.00 WIB belum diimplementasikan.

## Aturan bisnis yang disetujui
- Satu pesanan terpisah per **toko × dapur × tanggal kirim × jadwal kirim**.
- Admin Toko memilih toko yang menjadi tanggung jawabnya, dapur, tanggal kirim, jadwal kirim. Sistem memuat template SKU aktif dari middleware per dapur, pengguna **hanya mengisi Qty**.
- **Simpan Draft**: Qty disimpan. Draft dapat dibuka lagi kapan pun sebelum Kirim dan nilainya dapat ditambah, dikurangi, diubah menjadi 0, atau dihapus.
- **Kirim**: hanya baris **Qty ≥ 1** yang dipertahankan untuk konsolidasi; Qty pada formulir wajib **integer nonnegatif** (0, 1, 2, ...), jadi nilai desimal ditolak sejak Simpan Draft. Setelah Kirim, Admin Toko **tidak boleh mengedit** Qty maupun mengirim dua kali.
- Jika semua baris kosong/nol, status menjadi **NO_ORDER**, bukan error dan tidak membuat permintaan produksi.
- Draft yang belum Kirim **tidak ikut** konsolidasi produksi.
- Auto-submit pada **H-2 pukul 07.00 WIB** tetap aturan bisnis, tetapi worker otomatis **belum dibangun** pada milestone ini.
- Saat template SKU berubah setelah Draft disimpan, Qty lama tidak hilang diam-diam. Produk yang sudah tersimpan dalam Draft tetap terlihat dengan flag `active_in_template=false` agar bisa dikoreksi/diubah menjadi nol.
- Pesanan yang sudah Kirim/No Order tetap terbaca untuk histori, tetapi API menolak perubahan.

## API V1 — Login diperlukan

### 1. Buka formulir pesanan / Draft lama
```http
GET /api/v1/store-orders/?store_code=T_BAN&kitchen_code=JP&delivery_date=2026-11-07&schedule_code=SUBUH
```
Respons `id=null` dan `status=DRAFT` jika belum pernah disimpan, dengan `items` dari template. Jika sudah ada Draft, isi Qty berasal dari draft tersimpan, SKU lain `qty=0`.

### 2. Simpan atau ubah Draft
```http
POST /api/v1/store-orders/
Content-Type: application/json
```
```json
{
  "store_code": "T_BAN",
  "kitchen_code": "JP",
  "delivery_date": "2026-11-07",
  "schedule_code": "SUBUH",
  "items": [
    {"product_id": 123, "qty": "5"},
    {"product_id": 124, "qty": "0"},
    {"product_id": 125, "qty": "2"}
  ]
}
```
Saat menyimpan Draft, item dengan Qty 0 tidak perlu dipertahankan sebagai baris database (dimuat ulang sebagai 0 dari template). Nilai desimal seperti `0.5` atau `1.5` **ditolak** oleh API, termasuk saat menyimpan Draft. Input negatif, produk di luar template, duplikat ID, serta angka yang bukan integer ditolak. Request `items` merupakan **snapshot lengkap** nilai yang ingin disimpan; item yang tidak dikirim berarti Qty 0.

### 3. Kirim pesanan
```http
POST /api/v1/store-orders/42/send/
```
Contoh hasil:
```json
{
  "id": 42,
  "status": "KIRIM",
  "editable": false,
  "items_sent": 2,
  "excluded_below_one": 0
}
```
Kirim **tidak mengubah** master SKU Odoo maupun membuat MO. Formulir readonly setelah Kirim. Jika semua Qty kosong, status menjadi `NO_ORDER`.

## Akses, audit dan konkurensi
- API menggunakan autentikasi Django (SessionAuthentication), termasuk CSRF pada request melalui browser.
- Group `STORE` + baris `UserWarehouseAccess` pada toko terkait diperlukan untuk user toko; `ADMIN` atau superuser dapat mengakses semua toko untuk QA, dan identitas pelaku dicatat.
- Simpan Draft dan Kirim menggunakan transaksi PostgreSQL + `select_for_update()` untuk mencegah edit atau send bersamaan.
- Audit action `SAVE_DRAFT`, `KIRIM` / `NO_ORDER` mencatat actor dan perubahan Qty.
- Retry manual terhadap Kirim yang sudah sukses mengembalikan HTTP 409 dan tidak menggandakan order.
- `StoreOrder.order_date` pertama kali diambil dari tanggal WIB saat Draft dibuat; `delivery_date` disimpan terpisah.
- API belum mengelola jadwal produksi aktual dan belum mengirim dokumen ke Odoo.

## Penggunaan frontend ke depan
UI React bergaya SAP Fiori Horizon akan memakai satu grid untuk 50–700 SKU, pencarian dan navigasi keyboard Tab/Enter. Tombol **Simpan Draft** memanggil POST Draft. Tombol **Kirim** mengirim perubahan Draft lebih dahulu lalu memanggil endpoint send setelah konfirmasi pengguna. Saat membuka formulir, GET mengisi Qty lama. Tombol Kirim dinonaktifkan jika status sudah KIRIM/NO_ORDER.

## Uji coba di server
```bash
cd ~/RO-YUSSIAKMAL
git pull origin main
docker compose up -d --build --force-recreate api
docker compose exec api python manage.py test ro_core
```
Database migration baru tidak dibutuhkan pada milestone ini.

## Frontend yang sekarang tersedia
Workspace React dapat dibuka di **http://localhost:900/toko/** setelah build Docker versi terbaru. Login memakai Session+CSRF Django; untuk QA gunakan superuser Django. Manajemen jadwal default bisa dijalankan sekali dengan `docker compose exec api python manage.py seed_order_schedules`. Tabel Qty menampilkan daftar template dapur yang sudah diimpor lewat Excel, mengisi Draft dan memanggil endpoint Kirim yang dijelaskan di atas. Panduan: [Workspace Admin Toko](./WORKSPACE-ADMIN-TOKO.md).

## Perubahan aturan 2026-11-05 — Qty integer
- Qty pemesanan toko **hanya integer**, termasuk untuk Draft. Qty 0 tetap sah dan hanya Qty ≥1 diproses saat Kirim.
- API menolak nilai `1.5`, `0.5`, `1.0` dalam bentuk string, bilangan negatif, dan notasi ilmiah; frontend hanya mengizinkan digit.
- Draft lama yang masih memiliki Qty desimal tidak otomatis dibulatkan dan harus diedit menjadi integer sebelum Kirim.
- Kolom PostgreSQL tidak diubah karena persyaratan ini khusus data input toko; bahan baku Odoo bisa memakai satuan pecahan.

## Auto-submit terjadwal H-2 pukul 07.00 WIB
Backend sekarang memiliki command `auto_submit_store_orders` (default preview); timer harian Debian harus diaktifkan terpisah. Auto-submit mengubah Draft yang sudah ada untuk delivery date H+2 menjadi KIRIM atau NO_ORDER (Qty integer ≥1), serta mencatat `auto_submitted` dan audit. UI menampilkan label "Terkirim otomatis" untuk order final. Kebijakan Draft terlambat setelah cutoff belum diterapkan. Rujukan lengkap: [Auto-submit H-2](./AUTO-SUBMIT-H-2.md).

## Pemeriksaan pesanan melalui Django Admin
Menu `Store orders` dan `Store order lines` sekarang **hanya untuk melihat** rincian pesanan. Tabel detail memperlihatkan toko, dapur, tanggal kirim, jadwal, SKU, nama dan Qty integer (contoh data basis `78.0000` ditampilkan sebagai `78`). Admin tidak dapat menambah/mengedit/menghapus baris langsung: semua perubahan Draft wajib lewat Workspace Toko `/toko/`. Baris setelah KIRIM/NO_ORDER tidak boleh diedit. Kuantitas lama yang pecahan ditandai sebagai masalah data, bukan dibulatkan.

## Sesudah Kirim (November 2026)
Permintaan yang statusnya **KIRIM** segera tampil dalam antrean Admin Produksi, tanpa pengguna produksi harus mencari tanggal. Setelah konsolidasi rencana produksi yang berhasil disimpan (fitur lanjutan), status menjadi **PROSES_PRODUKSI**. Kedua status tersebut tetap terkunci bagi Admin Toko dan bisa dilihat read-only. Draft/NO_ORDER tidak tampil pada Admin Produksi.
