# Workspace Admin Produksi — Antrean Pesanan

**Keputusan operasional 6 November 2026:** Admin Produksi tidak perlu melihat Draft maupun No Order. Halaman utama adalah **antrean semua pesanan** dari toko yang sudah diserahkan, lintas tanggal, dapur dan jadwal.

## Status dan alur

`DRAFT` (Admin Toko; masih editable) → `KIRIM` (antrean Admin Produksi; belum dikonsolidasi) → `PROSES_PRODUKSI` (sudah masuk konsolidasi rencana produksi).

`NO_ORDER` adalah kondisi selesai tanpa pesanan dan **tidak masuk antrean Admin Produksi**.

**Implementasi terbaru:** selain antrean dan rekap, kini tersedia **Rencanakan** pada order KIRIM. Status baru berubah **KIRIM → PROSES_PRODUKSI setelah Simpan Konsolidasi berhasil secara atomik**; membuka rekap, pratinjau dan form tidak mengubah status.

## Tampilan yang digunakan

Kontrol **Teks − / +** di kanan atas mengubah semua ukuran font sebesar **1 poin per klik**, termasuk modal Rekap/Rencanakan/Lihat Rencana. Pilihan tersimpan di browser dan berlaku juga saat membuka Workspace Toko.

Buka `http://localhost:900/produksi/` dan login memakai superuser/ADMIN atau Group `PRODUCTION`.

- **Default Semua:** pesanan status KIRIM dan PROSES PRODUKSI seluruh tanggal/dapur/jadwal. Tidak ada filter tanggal otomatis.
- **Filter Kirim** untuk antrean siap konsolidasi; **Proses Produksi** untuk pesanan yang sudah dikonsolidasi.
- Tabel menampilkan Order ID, toko, tanggal kirim, dapur, jadwal kirim, jumlah SKU, total Qty, dan status.
- Kirim ditampilkan lebih dahulu; pagination **50 pesanan per halaman**, tombol Sebelumnya/Berikutnya. Jadi daftar tidak diam-diam dipotong ke 30 pesanan terbaru.
- Klik **Lihat rekap** untuk membuka **modal di atas antrean** (bukan panel panjang di bawah tabel atau pindah halaman). Rekap menunjukkan total per SKU pada lingkup tanggal kirim/dapur/jadwal pesanan, termasuk asal toko dan statusnya. Daftar dan filter di belakang modal tidak berubah; tekan **Tutup Rekap**, ikon ×, **Esc**, atau klik area luar modal untuk kembali. Fokus keyboard kembali ke tombol `Lihat rekap` yang tadi dipilih.
- Halaman ini **dapat menyimpan ProductionPlan lokal**, tetapi **belum membuat MO atau transfer Odoo**. Tanggal dan jadwal produksi diisi eksplisit oleh Admin Produksi.

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

Jumlah angka Qty kedua pesanan secara aritmetis adalah 1645, **tetapi itu bukan total dalam satu satuan yang boleh digunakan untuk produksi jika SKU mempunyai UoM berbeda**. Gunakan subtotal berdasarkan UoM/SKU dalam rekap. Jumlah SKU unik dihitung dari detail SKU, bukan jumlah baris masing-masing toko. Setelah deployment, kedua order harus muncul di tab **Semua** dan **Kirim**, tanpa memilih tanggal.

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
- Ketika fitur konsolidasi yang menulis ProductionPlan dibangun, **Admin Produksi wajib memilih tanggal produksi secara manual**, lalu status menjadi `PROSES_PRODUKSI` **hanya setelah konsolidasi berhasil disimpan secara atomik**. Hindari tombol yang cuma mengganti status tanpa membuat hasil konsolidasi.
- Auto-submit H-2 menghasilkan `KIRIM`; tidak otomatis memindahkan pesanan ke PROSES PRODUKSI.
- Aturan pesanan terlambat setelah cutoff H-2 07.00 WIB masih menjadi keputusan terpisah.

## Pola navigasi rekap — modal tanpa kehilangan fokus
- Modal memakai native HTML `dialog`, sehingga selama terbuka fokus keyboard berada di dalam modal dan daftar di belakang tidak aktif.
- Modal memiliki judul dan informasi tanggal/dapur/jadwal, indikator loading/error, total SKU/Qty, serta rincian yang bisa dibuka per SKU.
- Isi modal memiliki scroll sendiri agar halaman antrean tetap pada posisi semula.
- Ketika modal ditutup, fokus kembali ke tombol `Lihat rekap` pada baris yang sama; tidak reload antrean, tidak mengubah halaman pagination atau filter.
- Modal hanya membaca API rekap yang sudah ada; tidak mengubah status dan tidak menjalankan konsolidasi.

## Format Qty integer dan satuan produk (6 November 2026)
- Nilai kuantitas dari PostgreSQL bisa berbentuk `1232.0000` karena tipe `Decimal(18,4)`, walaupun pesanan toko **selalu integer**. Tampilan Admin Produksi sekarang memformatnya menjadi **1.232**, bukan `1232.0000`. Baris `120.0000` menjadi **120**. Tidak ada pembulatan otomatis untuk anomali pecahan historis.
- **UoM per SKU dibaca dari master produk middleware `Product.uom`, yang sudah disinkronkan read-only dari Odoo `product.product.uom_id`.** Jika UoM master kosong, tampilkan label sementara **pcs**.
- Di modal rekap, setiap SKU dan rincian permintaan toko menampilkan Qty dan **satuan produk yang sama**. Contoh `120 Lusin` bila master menyebut Lusin; `120 pcs` bila master kosong.
- Total Qty pada daftar pesanan hanya diberi satuan tunggal bila seluruh SKU punya UoM yang sama. Jika satu pesanan memiliki campuran UoM, UI menampilkan **subtotal terpisah untuk setiap UoM**, bukan satu angka gabungan.
- Perbaikan ini **tidak menambahkan migrasi**, tidak mengubah data pesanan, template, master Odoo, atau status. API menormalkan Qty integral ke string integer; Qty pecahan historis tidak ditampilkan sebagai angka operasional, melainkan ditandai **Perlu koreksi Qty**, dan rekap per SKU tetap memvalidasi integritas.
- Verifikasi UoM asli SKU tertentu pada database Debian (read-only):
  ```bash
  docker compose exec api python manage.py shell -c "from ro_core.models import Product; print(list(Product.objects.filter(sku='10005').values('sku','name','uom')))"
  ```

## Pengamanan wajib Qty tanpa desimal dan multi-satuan
- **Tampilan operasional tidak pernah menampilkan Qty desimal.** Bilangan bulat tersimpan `1.0000` tampil `1`, `1232.0000` tampil `1.232`. Data lama dengan pecahan sungguhan **tidak dibulatkan**; muncul peringatan **Perlu koreksi Qty** dalam daftar produksi. Rekap yang memuat data bermasalah akan menolak dengan HTTP 409 sampai datanya diperbaiki.
- **Jangan menjumlahkan satuan berlainan seolah sejenis.** Total Qty `1 Kg` ditambah `500 gram` **bukan** `501 unit`. Daftar dan ringkasan rekap menampilkan subtotal **per UoM** (`1 Kg · 500 gram`) tanpa konversi terselubung.
- Produk yang menggunakan UoM sama tetap dapat dijumlahkan; setiap baris SKU memakai UoM asli dari `Product.uom` bila ada, fallback `pcs` bila kosong.
- UoM per baris pesanan belum tersedia: `StoreOrderLine` sekarang punya satu Qty per SKU dan unitnya mengikuti master Produk. Multi-UoM untuk **satu SKU** dengan baris `1 Kg` dan `500 gram` memerlukan keputusan dan perubahan skema lanjutan. Ini **belum** diimplementasikan. Jangan menyimpulkan adanya konversi otomatis.
- Perubahan ini hanya pemeriksaan dan penyajian API/React, tanpa migrasi atau mutasi data/Odoo. `qty_total=null` menandakan total tidak aman untuk dinyatakan sebagai satu angka; baca `qty_by_uom` dan `qty_invalid`.

## Kontrak bisnis konsolidasi V1 (tersedia) dan fitur tahap berikutnya

Keputusan sudah pasti: **tanggal produksi dipilih manual oleh Admin Produksi**, bukan default H-1/H-2. Untuk pesanan `JP / SUBUH / kirim 2026-11-07`, operator harus mengisi tanggal produksi sebelum menyimpan.

Lihat [Kontrak Bisnis Konsolidasi Produksi V1](./KONTRAK-KONSOLIDASI-PRODUKSI-V1.md) untuk urutan operator, kontrak Qty Requested / Qty Planned, constraint sumber StoreOrder, audit, status atomik dan acceptance criteria.

**Fitur konsolidasi awal telah tersedia:** tombol Rencanakan pada order KIRIM membuka form tabel tiga Qty plus selisih, menyimpan rencana lokal, dan setelah berhasil mengubah status sumber. Larangan memecah jadwal kirim toko tetap berlaku. Detail dan batas V1 ada pada Kontrak Konsolidasi Produksi V1.

## Jadwal produksi terpisah dan kapasitas SKU

- **Tanggal produksi** ditetapkan manual oleh Admin Produksi. **Jadwal produksi** merupakan dimensi perencanaan yang berbeda dari **jadwal kirim** yang sudah ditentukan Admin Toko.
- SKU yang sama boleh diproduksi pada tanggal produksi sama namun dalam jadwal produksi berbeda untuk kelompok permintaan pengiriman yang berbeda.
- Admin Produksi **tidak boleh** memecah permintaan `500 Pcs` jadwal kirim `SUBUH` menjadi `250 SUBUH + 250 PAGI`, atau mengubah tanggal/jadwal kirim tanpa keputusan Admin Toko.
- Rancangan form perencanaan **wajib menampilkan** `Qty Pesan (read-only) | Qty Kapasitas Produksi (read-only) | Qty Produksi (input)` per SKU dengan UoM. Kapasitas didapat dari `ProductCapacity.max_qty` untuk **SKU × jadwal produksi** (bukan jadwal kirim), dan harus mempertimbangkan kapasitas yang sudah dipakai rencana lain di tanggal/jadwal produksi yang sama.
- Bila kapasitas tidak ada, tampilkan **Kapasitas belum diatur**, bukan nol atau tak terbatas. Bila Qty Pesan melebihi kapasitas, tampilkan kekurangan tanpa memindahkan jadwal pengiriman otomatis.
- **Keputusan disepakati:** contoh Qty Pesan **500 Pcs**, kapasitas tersedia **400 Pcs**, Qty Produksi **400 Pcs** boleh **disimpan** sebagai konsolidasi lokal, asalkan **Qty Kekurangan 100 Pcs** juga tersimpan dan terlihat di layar serta histori. Permintaan toko **500 Pcs SUBUH** tidak diubah dan tidak otomatis dinyatakan terpenuhi.
- Hitung `qty_shortfall = max(0, qty_requested - qty_planned)` terpisah dari `capacity_gap = max(0, qty_requested - capacity_available)`. Jangan menganggap keduanya selalu sama. Qty Produksi di atas kapasitas dan mekanisme tindak lanjut kekurangan masih perlu keputusan.
- **Sudah tersedia dalam V1:** jadwal produksi terpisah di ProductionPlan, tabel tiga Qty, Simpan Konsolidasi, histori rencana dan Qty Kekurangan. **Belum tersedia:** MO/BoM, transfer Odoo, revisi/rencana split lintas jadwal untuk satu scope kirim, dan pemenuhan per toko.
- Kontrak rinci: [Konsolidasi Produksi V1](./KONTRAK-KONSOLIDASI-PRODUKSI-V1.md).

## Menggunakan Konsolidasi Produksi V1

1. Buka `/produksi/`; cari pesanan **KIRIM**, lalu klik **Rencanakan** untuk membuka **pop-up/modal di atas antrean** (bukan mengganti halaman atau membuat form di bawah tabel). Semua KIRIM dengan dapur, tanggal kirim dan jadwal kirim sama akan digabung; bukan hanya toko pada baris yang diklik.
2. Pastikan **tanggal/jadwal kirim** terlihat read-only sesuai toko. Pilih **Tanggal Produksi** manual dan **Jadwal Produksi** pada field terpisah (tidak ada default).
3. Tinjau **Qty Pesan, Hasil 1 Resep BoM, Kapasitas master, Terpakai, Tersisa** per SKU/UoM. Isi **Qty Produksi** manual sebagai bilangan bulat positif, maksimal kapasitas tersisa. Angka boleh melebihi Qty Pesan; tidak ada pembulatan otomatis.
4. Contoh: diminta **500 Pcs**, kapasitas tersedia **400 Pcs**, diisi Qty Produksi **400 Pcs** → tabel menampilkan **Kekurangan 100 Pcs**. **Simpan Konsolidasi tetap boleh**, tanpa mengubah 500 Pcs/jadwal kirim toko.
5. Jika kapasitas master belum tersedia untuk salah satu SKU, Simpan diblokir dengan keterangan jelas. Perbaiki kapasitas melalui konfigurasi master terlebih dahulu. Jangan mengasumsikan kapasitas kosong berarti tidak terbatas.
6. Setelah berhasil, semua order sumber menjadi **PROSES_PRODUKSI** dan memiliki aksi **Lihat Rencana**; histori menyimpan detail kebutuhan, produksi, kapasitas, dan kekurangan. **Tidak ada MO Odoo**.

Modal Rencanakan dan Lihat Rencana menyediakan **pencarian SKU atau nama produk**, tanpa membedakan huruf besar/kecil. Jumlah hasil ditampilkan; **Hapus pencarian** menampilkan seluruh SKU kembali. Pencarian hanya menyaring tampilan: Qty yang diisi tetap tersimpan di formulir, validasi tetap memeriksa semua SKU, dan Simpan Konsolidasi tetap menyertakan seluruh SKU dalam lingkup pesanan.

### API konsolidasi (PRODUCTION/ADMIN, session + CSRF)
```http
GET /api/v1/production/consolidation/preview/?kitchen_code=JP&delivery_date=2026-11-07&delivery_schedule_code=SUBUH&production_date=2026-11-06&production_schedule_code=PAGI
POST /api/v1/production/consolidations/
GET /api/v1/production/consolidations/{plan_id}/
```

Contoh POST (ganti ID hasil preview):
```json
{
  "kitchen_code": "JP",
  "delivery_date": "2026-11-07",
  "delivery_schedule_code": "SUBUH",
  "production_date": "2026-11-06",
  "production_schedule_code": "PAGI",
  "order_ids": [1, 2],
  "items": [{"product_id": 123, "qty_planned": "400"}]
}
```
Tombol di frontend adalah cara utama memakai API, contoh POST bukan instruksi untuk langsung dijalankan dengan ID rekaan.

### Deploy perubahan skema
```bash
cd ~/RO-YUSSIAKMAL
git pull origin main
docker compose up -d --build --force-recreate api
docker compose exec api python manage.py migrate --noinput
docker compose exec api python manage.py check
```
**Migration 0004** tidak membuat jadwal produksi historis dari jadwal kirim; `production_schedule=NULL` pada plan lama berarti belum diketahui. ProdPlanLine batch/MO boleh NULL sampai tahap MO. Pastikan backup PostgreSQL sebelum migrasi skema.

## Pola navigasi Rencanakan & Lihat Rencana — modal seperti Lihat Rekap

- Tombol **Lihat Rekap**, **Rencanakan**, dan **Lihat Rencana** semuanya memakai native HTML `dialog` yang tampil **di atas halaman antrean**, bukan menambah konten di bawah, bukan pindah route, dan bukan membuka jendela browser baru.
- Modal Rencanakan cukup besar untuk tabel kapasitas/Qty SKU yang banyak. Isi mempunyai **scroll vertikal sendiri** dan tabel dapat scroll horizontal pada layar sempit; header judul dan footer aksi tetap terlihat.
- Saat modal dibuka, fokus pindah ke tombol ×. Tekan **×**, **Batal / Tutup**, **Esc**, atau klik luar modal untuk menutup. Saat ditutup tanpa simpan, fokus kembali ke tombol Rencanakan atau Lihat Rencana pada baris asal, tanpa reload/ubah filter/page/scroll antrean.
- Bila **Simpan Konsolidasi** berhasil, modal berubah menjadi histori **Rencana Produksi #ID** tanpa membuang konteks antrean. Setelah modal ditutup, daftar dimuat ulang dan fokus diarahkan ke **Lihat Rencana** pada baris asal; jika baris hilang karena filter status, fokus ke tab filter aktif.
- Saat penyimpanan sedang berjalan, tombol tutup dan tindakan Esc/backdrop tidak menutup dialog agar status penyimpanan tidak ambigu.
- Seluruh perhitungan Qty, kapasitas, kekurangan, status dan histori **tidak berubah** karena perubahan UX modal ini. Tidak ada migrasi baru.


## Mengisi kapasitas saat memasukkan SKU ke dapur
Batas kapasitas di perencanaan Admin Produksi berasal dari master `ProductCapacity.max_qty` per SKU × jadwal produksi. Admin sekarang mengatur kapasitas **langsung dari Django Admin → Production Assignments**, bersamaan dengan menugaskan SKU ke dapur. Template Excel yang sama juga menyediakan `KAPASITAS_SUBUH`, `KAPASITAS_PAGI`, dst. sesuai jadwal aktif; impor penugasan+kapasitas atomik.
Qty kapasitas harus bilangan bulat dalam UoM asli dari Odoo. Kosong tetap **Belum diatur** (dan menahan proses simpan konsolidasi), bukan nol atau tanpa batas. Kapasitas 0 adalah nol. Tidak ada migrasi skema pada perubahan alur input ini.
Panduan: [Template SKU per Dapur](./TEMPLATE-PEMESANAN.md).

Menu teknis Product Capacities hanya untuk inspeksi; gunakan Production Assignments untuk semua perubahan kapasitas. Hal ini menjaga perubahan kapasitas tetap diaudit bersama perubahan template.


## Pembaruan 8 November 2026 — Informasi hasil 1 resep BoM

- Kolom **Hasil 1 Resep BoM** menginformasikan output resep dari master Odoo, misalnya **100 Pcs**. Informasi ini tidak menentukan jumlah resep, mengisi Qty, atau membulatkan produksi otomatis.
- **Qty Produksi** (`qty_planned`) tetap diisi manual oleh Admin Produksi. Untuk kebutuhan 150 dan kapasitas 300, operator boleh memilih 200 atau 300; sistem menyimpan persis angka yang dimasukkan, selama integer positif dan tidak melebihi kapasitas tersisa. Batas sementara Qty Planned ≤ Qty Requested digantikan oleh keputusan ini.
- Kekurangan = `max(0, requested - planned)`. Kelebihan = `max(0, planned - requested)`, hanya ditampilkan tanpa alokasi otomatis. Pesanan dan jadwal kirim toko tetap utuh.
- Informasi BoM yang belum tersedia diberi label **Belum tersedia**, tanpa menebak resep atau memblokir penyimpanan manual karena informasi tersebut. `qty_mo` dan `batch_qty` tetap NULL pada rencana baru; tidak ada perhitungan batch atau MO Odoo pada tahap ini.
- Kelebihan belum otomatis dijadikan WIP atau dibagi prorata. Pengaturan alokasi aktual tetap di tahap Packing; kebijakan WIP/prorata belum diputuskan.
