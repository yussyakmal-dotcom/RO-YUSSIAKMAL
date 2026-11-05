# Workspace Admin Produksi — Antrean Pesanan

**Keputusan operasional 6 November 2026:** Admin Produksi tidak perlu melihat Draft maupun No Order. Halaman utama adalah **antrean semua pesanan** dari toko yang sudah diserahkan, lintas tanggal, dapur dan jadwal.

## Status dan alur

`DRAFT` (Admin Toko; masih editable) → `KIRIM` (antrean Admin Produksi; belum dikonsolidasi) → `PROSES_PRODUKSI` (sudah masuk konsolidasi rencana produksi).

`NO_ORDER` adalah kondisi selesai tanpa pesanan dan **tidak masuk antrean Admin Produksi**.

**Penting:** perubahan kode ini menambahkan status `PROSES_PRODUKSI`, tampilan antrean global, serta dukungan rekap untuk status tersebut. **Belum ada tombol untuk mengubah KIRIM menjadi PROSES_PRODUKSI**, karena itu harus terjadi dalam transaksi yang sama ketika konsolidasi rencana benar-benar dibuat dan disimpan. Membuka atau melihat rekap tidak dianggap konsolidasi; status tidak berubah diam-diam.

## Tampilan yang digunakan

Buka `http://localhost:900/produksi/` dan login memakai superuser/ADMIN atau Group `PRODUCTION`.

- **Default Semua:** pesanan status KIRIM dan PROSES PRODUKSI seluruh tanggal/dapur/jadwal. Tidak ada filter tanggal otomatis.
- **Filter Kirim** untuk antrean siap konsolidasi; **Proses Produksi** untuk pesanan yang sudah dikonsolidasi.
- Tabel menampilkan Order ID, toko, tanggal kirim, dapur, jadwal kirim, jumlah SKU, total Qty, dan status.
- Kirim ditampilkan lebih dahulu; pagination **50 pesanan per halaman**, tombol Sebelumnya/Berikutnya. Jadi daftar tidak diam-diam dipotong ke 30 pesanan terbaru.
- Klik **Lihat rincian** untuk melihat Qty per SKU yang dikumpulkan dalam lingkup tanggal kirim/dapur/jadwal pesanan tersebut, termasuk asal toko dan status masing-masing.
- Halaman ini **belum membuat ProductionPlan, MO, atau transfer**; tanggal produksi masih memerlukan keputusan SOP.

## API

### Daftar antrean global
```http
GET /api/v1/production/orders/?status=ALL&page=1
```
`status` dapat berisi `ALL`, `KIRIM`, `PROSES_PRODUKSI`; nilai `DRAFT` dan `NO_ORDER` ditolak. `page` dimulai dari 1. Hasil memiliki `total`, `counts`, `has_more`, dan `items`. Hanya Group PRODUCTION/ADMIN/superuser yang dapat mengaksesnya.

### Rincian rekap SKU
```http
GET /api/v1/production/demand/?delivery_date=2026-11-07&kitchen_code=JP&schedule_code=SUBUH
```
Hanya `KIRIM` dan `PROSES_PRODUKSI` yang berkontribusi pada Qty total. Jika suatu item sudah berada di PROSES PRODUKSI, item tidak dihitung dua kali. SKU yang sudah dihapus/nonaktif pada template tetap diperhitungkan jika pesanan historisnya memang final. Jika ada Qty pecahan historis, API menolak rekap agar tidak membulatkan tanpa izin.

API lama `/api/v1/production/recent-orders/` masih tersedia untuk kompatibilitas tetapi **bukan lagi sumber halaman utama**.

## Pengujian menggunakan data Debian

Pesanan yang telah diverifikasi:

| Order ID | Toko | Dapur | Tanggal kirim | Jadwal | Status | Qty |
|---|---|---|---|---|---|---:|
| 1 | T_BAN | JP | 2026-11-07 | SUBUH | KIRIM | 1232 |
| 2 | T_KD | JP | 2026-11-07 | SUBUH | KIRIM | 413 |

Jumlah dua pesanan **1645 unit**, tetapi jumlah SKU unik dihitung dari detail SKU, bukan dari jumlah baris masing-masing toko. Setelah deployment, kedua order harus muncul di tab **Semua** dan **Kirim**, tanpa memilih tanggal.

```bash
cd ~/RO-YUSSIAKMAL
git pull origin main
docker compose up -d --build --force-recreate api
docker compose exec api python manage.py migrate --noinput
docker compose exec api python manage.py check
```

Buka `http://localhost:900/produksi/` lalu cek Order #1 dan #2. Tidak ada perubahan data pesanan saat menjalankan migrasi ini; migrasi hanya memperluas pilihan status dan panjang field.

## Pengamanan

- Admin Toko masih bisa mengedit hanya saat status `DRAFT`. Setelah `KIRIM` atau `PROSES_PRODUKSI`, pengeditan dilarang.
- Membuka antrean/rekap tidak mengubah status, Qty atau Odoo.
- Ketika fitur konsolidasi yang menulis ProductionPlan dibangun, status menjadi `PROSES_PRODUKSI` **hanya setelah konsolidasi berhasil disimpan secara atomik**. Hindari tombol yang cuma mengganti status tanpa membuat hasil konsolidasi.
- Auto-submit H-2 menghasilkan `KIRIM`; tidak otomatis memindahkan pesanan ke PROSES PRODUKSI.
- Aturan pesanan terlambat setelah cutoff H-2 07.00 WIB masih menjadi keputusan terpisah.
