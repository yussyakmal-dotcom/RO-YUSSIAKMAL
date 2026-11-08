# RO Middleware — Django V1 bootstrap

Aplikasi input dan konsolidasi produk, bahan, produksi, dan distribusi. Odoo tetap sumber kebenaran stok dan transaksi.

Dokumentasi: [PRD](docs/PRD.md) · [DDL](docs/DDL.md) · [Django Models](docs/DJANGO-MODELS.md) · [Decision Log](docs/DECISION-LOG.md) · [Odoo Connector](docs/ODOO-CONNECTOR.md) · [Template Pemesanan](docs/TEMPLATE-PEMESANAN.md) · [Draft/Kirim](docs/ADMIN-TOKO-DRAFT-KIRIM.md) · [Frontend Admin Toko](docs/WORKSPACE-ADMIN-TOKO.md) · [Rekap Admin Produksi](docs/WORKSPACE-ADMIN-PRODUKSI.md) · [Auto-submit H-2](docs/AUTO-SUBMIT-H-2.md)

## Jalankan pengembangan lokal

```bash
cp .env.example .env
# Edit .env: ganti DJANGO_SECRET_KEY dan POSTGRES_PASSWORD
docker compose up --build -d
docker compose exec api python manage.py createsuperuser
curl http://127.0.0.1:900/health/
```

Workspace Admin Toko: **http://127.0.0.1:900/toko/** (login menggunakan superuser atau Group STORE yang punya akses toko). Django Admin tetap di http://127.0.0.1:900/admin/. Service default hanya dibuka di localhost; PostgreSQL tidak diekspos ke host.

```bash
docker compose exec api python manage.py check
docker compose exec api python manage.py makemigrations --check --dry-run
docker compose exec api python manage.py test ro_core
docker compose logs -f api
```

## Odoo 19 master connector (read-only)

Set `ODOO_BASE_URL`, optional `ODOO_DATABASE`, and `ODOO_API_KEY` inside your untracked `.env` file, then recreate the API container so it loads the new environment. **Never commit API keys.**

```bash
docker compose up -d --build --force-recreate api
docker compose exec api python manage.py odoo_probe
docker compose exec api python manage.py odoo_sync_master          # preview, no writes
docker compose exec api python manage.py odoo_sync_master --apply  # middleware database only
```

Read [connector setup and limitations](docs/ODOO-CONNECTOR.md) before applying. Mapping SKU-to-kitchen remains middleware-owned and is never overwritten by routine sync. Live Odoo integration is not configured until credentials are supplied locally.

## Menentukan dapur produksi dari Odoo Operation Type

**Koreksi penting:** Product Category hanya mengelompokkan produk; **bukan penentu dapur produksi**. Saat MO dibuat, Odoo memakai `mrp.production.picking_type_id` (Manufacturing Operation Type). Perintah mapping kategori lama sengaja dinonaktifkan, termasuk `--apply`.

Lihat daftar Operation Type manufaktur yang benar dari tenant Anda (READ-ONLY):

```bash
docker compose exec api python manage.py odoo_mo_operation_types
```

Hasilnya menunjukkan ID Operation Type, nama, warehouse dan lokasi default. Setelah diverifikasi, kita dapat menghubungkan dapur/warehouse middleware ke Operation Type Odoo **dengan konfigurasi eksplisit**, bukan menebak lewat kategori. Pemetaan SKU yang sudah ada tidak dimodifikasi oleh pemeriksaan ini. Lihat [panduan](docs/ODOO-CONNECTOR.md#verifikasi-manufacturing-operation-type).

## Template pemesanan per dapur (Excel manual)

Administrator mengatur SKU setiap dapur melalui **Django Admin → Production Assignments**. Klik **Download Format Excel** / **Upload Template Excel** untuk mengelola urutan, status Aktif/Nonaktif, dan penugasan SKU per dapur. Product Category bukan sumber assignment.

```bash
git pull origin main
docker compose up -d --build
docker compose exec api python manage.py migrate --noinput
curl http://127.0.0.1:900/health/
```

API daftar SKU aktif (perlu autentikasi): `GET /api/v1/order-templates/PST/`. Mengembalikan `id, sku, name, qty:0`. UI input Qty/Draft/Kirim React tersedia di `/toko/`.

Petunjuk dan aturan impor: [Template Pemesanan per Dapur](docs/TEMPLATE-PEMESANAN.md).

## Admin Toko — Draft dan Kirim (API)

Pesanan per **toko × dapur × tanggal kirim × jadwal**. `Simpan Draft` dapat dibuka dan diedit lagi; `Kirim` hanya mempertahankan Qty **>= 1** dan mengunci pesanan. Semua nol → status `NO_ORDER`.

- `GET /api/v1/store-orders/?store_code=T_BAN&kitchen_code=JP&delivery_date=2026-11-07&schedule_code=SUBUH` — buka template dan Qty draft lama
- `POST /api/v1/store-orders/` — simpan atau ganti Qty Draft
- `POST /api/v1/store-orders/<id>/send/` — Kirim (Qty >= 1), tidak dapat diedit lagi

API membutuhkan akun login, role dan akses toko. Lihat [aturan serta contoh payload](docs/ADMIN-TOKO-DRAFT-KIRIM.md). Frontend React tersedia di `/toko/`; auto-submit 07.00 belum dibangun.

## Workspace Admin Toko — React

Setelah `git pull origin main`, jalankan `docker compose up -d --build --force-recreate api` untuk membangun image Django beserta React/Vite. **Host port tetap 900**; Node hanya berjalan pada tahap Docker build.

Siapkan tiga jadwal default jika belum ada:
```bash
docker compose exec api python manage.py seed_order_schedules
```
Lalu buka `http://localhost:900/toko/`. Login pertama dapat memakai superuser Django yang sudah ada. Akun toko biasa membutuhkan Group `STORE` dan `UserWarehouseAccess` untuk toko masing-masing. **Simpan Draft** dapat dibuka dan diedit ulang; **Kirim** menyimpan hanya Qty ≥1 dan mengunci pesanan.

Panduan lengkap: [Workspace Admin Toko](docs/WORKSPACE-ADMIN-TOKO.md). Build frontend memerlukan Node 22 pada Docker multi-stage, sehingga tidak perlu memasang Node lokal. `compose.yaml` tidak lagi bind-mount backend agar asset frontend tidak tertimpa. Data PostgreSQL tidak dihapus oleh proses rebuild.

Schema dieksekusi melalui Django migrations. Jangan jalankan SQL docs/DDL.md secara manual. Proyek ini *scaffold development*, belum memiliki seluruh workflow operasional, integrasi transaksi Odoo, atau deployment production.

Jangan commit .env, credential Odoo, file backup. Hindari `docker compose down -v` jika data PostgreSQL ingin dipertahankan.

## Qty integer pada Workspace Admin Toko
Qty input pesanan toko menerima **hanya bilangan bulat**: `0, 1, 2, ...`. Tidak boleh desimal. Draft tetap dapat dibuka dan diedit, Kirim hanya memproses Qty ≥1, semua nol → No Order. Validasi juga dilakukan server-side, dan tidak ada perubahan/migration DB untuk aturan ini.

## Auto-submit H-2 pukul 07.00 WIB (backend + timer opsional)

Perintah default adalah **preview tanpa perubahan**:
```bash
docker compose exec api python manage.py auto_submit_store_orders
```

Setelah preview, sistem dapat dijadwalkan pukul **07:00 WIB** menggunakan template **systemd timer** di `deploy/systemd/`. Timer **tidak otomatis aktif setelah git pull atau Docker rebuild**; pemasangan dan aktivasi memerlukan langkah eksplisit pada Debian. Setelah diaktifkan, `--apply` hanya memfinalisasi Draft yang sudah ada untuk tanggal kirim H+2: Qty integer ≥ 1 → KIRIM, semuanya nol → NO_ORDER, lalu terkunci dan dicatat audit. Tidak membuat MO maupun menulis Odoo.

**Peringatan operasional:** Draft yang baru dibuat setelah run 07:00 belum dicegah/diproses ulang; kebijakan input terlambat masih perlu ditetapkan sebelum dijadikan sistem tanpa pengawasan. Baca [panduan timer dan batas V1](docs/AUTO-SUBMIT-H-2.md) sebelum mengaktifkan jadwal.

## Tampilan teknis Store Order / Store Order Line di Django Admin

Menu **Store orders** dan **Store order lines** pada `/admin/` adalah halaman **pemeriksaan read-only**. Daftarnya menampilkan toko, dapur, tanggal kirim, jadwal, SKU, nama produk, Qty, serta status pesanan; bukan lagi label `StoreOrderLine object (18)`. Qty integer ditampilkan tanpa `.0000` (misalnya `78`), sedangkan data lama yang benar-benar pecahan diberi tanda perlu koreksi.

**Jangan mengubah pesanan lewat Django Admin.** Draft diubah pada `/toko/`; setelah Kirim atau NO_ORDER datanya terkunci. Kolom PostgreSQL tetap Decimal(18,4) demi kompatibilitas, tetapi UI/API toko tetap menerima Qty integer saja. Tidak ada migration database untuk perbaikan tampilan ini.

## Workspace Admin Produksi — Antrean dan Rekap (implementasi saat ini)

Buka **http://localhost:900/produksi/** dengan akun Group `PRODUCTION`, `ADMIN`, atau superuser.

- Halaman pertama menampilkan **seluruh pesanan KIRIM dan PROSES_PRODUKSI**, lintas tanggal/dapur/jadwal, dengan tab **Semua / Kirim / Proses Produksi** dan pagination 50 order.
- **DRAFT**, **NO_ORDER**, dan toko yang belum membuat order **tidak ditampilkan** kepada Admin Produksi.
- Tombol **Lihat rekap** membuka pop-up baca-saja yang menunjukkan Qty per SKU dan asal toko pada dapur × tanggal kirim × jadwal kirim yang sama. Klik **Tutup Rekap**, ×, atau Esc untuk kembali fokus ke baris semula tanpa mengubah filter/posisi daftar.
- **Qty operasional hanya ditampilkan sebagai angka bulat** tanpa ekor `.0000`. Qty historis pecahan diberi peringatan **Perlu koreksi Qty**, bukan dibulatkan. UoM berasal dari `Product.uom` hasil sync Odoo (fallback **pcs** bila kosong). SKU dengan UoM berbeda tidak dijumlahkan sebagai satu angka: tampilkan subtotal per UoM.
- Admin Produksi **sudah bisa menyimpan ProductionPlan lokal** lewat **Rencanakan**; setelah simpan atomik, sumber berubah `PROSES_PRODUKSI` dan **Lihat Rencana** menampilkan kekurangan. **Lihat Rekap** tetap baca-saja, dan MO/transfer Odoo belum dibuat.

API read-only:
```text
GET /api/v1/production/orders/?status=ALL&page=1
GET /api/v1/production/demand/?delivery_date=2026-11-07&kitchen_code=JP&schedule_code=SUBUH
```

Endpoint lama `/api/v1/production/recent-orders/` masih tersedia untuk kompatibilitas tetapi **bukan** sumber UI utama. Status PROSES_PRODUKSI dan migration 0003 telah tersedia, namun perpindahan status otomatis baru dilakukan setelah proses konsolidasi nyata dibangun.

Panduan: [Workspace Admin Produksi](docs/WORKSPACE-ADMIN-PRODUKSI.md).

## Milestone berikutnya — Kontrak Konsolidasi Produksi V1

**Keputusan bisnis terbaru (2026-11-06): tanggal produksi ditentukan manual oleh Admin Produksi**, bukan dihitung H-1/H-2 atau diisi otomatis menurut jadwal kirim. Untuk lingkup `JP / SUBUH / kirim 2026-11-07`, operator memilih tanggal produksinya sendiri sebelum simpan.

Dokumen desain berikutnya: **[Kontrak Bisnis Konsolidasi Produksi V1](docs/KONTRAK-KONSOLIDASI-PRODUKSI-V1.md)**. Kontrak mencakup sumber hanya order KIRIM, Qty Requested → Planned, audit, pelacakan order asal, anti-duplikasi, transaksi atomik dan status menjadi PROSES_PRODUKSI setelah rencana tersimpan. **Konsolidasi produksi lokal V1 kini telah diimplementasikan** (tanggal/jadwal produksi eksplisit, kapasitas, Qty Pesan/Produksi/Kekurangan, histori). MO/transfer Odoo belum tersedia. **Jadwal produksi wajib disimpan terpisah dari jadwal kirim**, dan layar perencanaan yang kini tersedia memperlihatkan **Qty Pesan, Qty Kapasitas Produksi, dan Qty Produksi**. Admin Produksi tidak boleh memecah/mengubah permintaan pengiriman **500 Pcs SUBUH** menjadi **250 SUBUH + 250 PAGI**. Qty Kapasitas berasal dari ProductCapacity berdasarkan SKU × **jadwal produksi**; kekurangan kapasitas harus ditampilkan. **Keputusan terbaru:** jika Qty Pesan **500 Pcs**, kapasitas tersedia **400 Pcs**, Admin Produksi **boleh menyimpan Qty Produksi 400 Pcs dengan kekurangan 100 Pcs tetap tercatat/terlihat**. Qty dan jadwal kirim toko tidak berubah dan kekurangan bukan pemenuhan otomatis. Perhitungan kekurangan rencana `max(0, requested - planned)` dipisahkan dari selisih kapasitas `max(0, requested - available_capacity)`. Kebijakan alokasi pelaksanaan lintas jadwal tanpa mengubah jadwal kirim, Qty Produksi melebihi kapasitas, approval dan tindak lanjut kekurangan masih perlu disepakati. Migration `0004` dan layar perencanaan kini telah tersedia; integrasi MO/BoM/Odoo belum diimplementasikan.

Untuk menyegarkan aplikasi di Debian **hanya setelah ada perubahan kode yang sudah di-merge**:
```bash
cd ~/RO-YUSSIAKMAL
git pull origin main
docker compose up -d --build --force-recreate api
```

PR dokumentasi kontrak ini **tidak memerlukan rebuild, migrasi database, atau perubahan Odoo**.

## Konsolidasi Produksi V1 (local, belum Odoo)
Pada `/produksi/`, tombol **Rencanakan** dan **Lihat Rencana** sekarang membuka **modal/pop-up di atas antrean**, sama seperti **Lihat Rekap**. Daftar, filter, pagination dan posisi scroll tetap berada di belakang; pengguna tidak berpindah halaman atau menggulir ke bawah untuk mencari form. Operator wajib memilih **Tanggal Produksi manual** dan **Jadwal Produksi**, terpisah dari tanggal/jadwal kirim toko yang read-only. Tabel menampilkan per SKU `Qty Pesan | Kapasitas Master | Terpakai | Tersisa | Qty Produksi | Kekurangan`.
Qty Produksi diisi manual oleh Admin Produksi, harus integer positif dan tidak melebihi **kapasitas tersisa**. Angka boleh melebihi Qty Pesan. Kolom **Hasil 1 Resep BoM** hanya memberikan informasi hasil per resep (mis. 100 Pcs); sistem tidak memilih jumlah resep atau membulatkan Qty otomatis. Jika pesanan 500 Pcs, kapasitas 400 Pcs, rencana 400 Pcs boleh disimpan dengan **100 Pcs kekurangan** tersimpan dalam histori. Tidak ada split/migrasi jadwal kirim toko. Master kapasitas belum diatur → simpan ditolak hingga dikonfigurasi.
Simpan mencatat ProductionPlan/Line, snapshot sumber StoreOrder, AuditLog, Qty Kekurangan, dan memindah status KIRIM → PROSES_PRODUKSI **atomik**. Setelah tersimpan, tombol **Lihat Rencana** membuka histori kekurangan sebagai pop-up baca-saja. **Tidak membuat MO, tidak menghitung BoM batch, tidak mengirim Odoo**.
`ProductionPlan.production_schedule` kini terpisah dari `delivery_schedule` (migration `0004`, production_schedule historis NULL, tidak ditebak). Sebelum deploy, pastikan **backup PostgreSQL** tersedia. Setelah merge:
```bash
cd ~/RO-YUSSIAKMAL
git pull origin main
docker compose up -d --build --force-recreate api
docker compose exec api python manage.py migrate --noinput
docker compose exec api python manage.py check
```
Panduan: [Admin Produksi](docs/WORKSPACE-ADMIN-PRODUKSI.md), [Kontrak](docs/KONTRAK-KONSOLIDASI-PRODUKSI-V1.md).

### Perilaku modal Rencanakan dan Lihat Rencana
- Klik **Rencanakan** atau **Lihat Rencana** membuka `<dialog>` modal native, **bukan** halaman baru, konten inline yang turun, atau tab browser baru. Popup lebar/tinggi responsif dengan scroll di dalam, header dan tombol aksi tetap terlihat.
- Tekan ×, tombol **Batal / Tutup** (atau **Tutup Rencana**), **Esc**, atau area backdrop untuk kembali ke daftar. Fokus kembali ke tombol pemicu; filter, pagination, dan posisi daftar tetap terjaga. Membuka/menutup tanpa simpan tidak memanggil ulang inbox.
- Setelah konsolidasi berhasil tersimpan, histori tetap tampil di modal. Inbox diperbarui **ketika modal ditutup**, lalu fokus diarahkan ke tombol pengganti **Lihat Rencana** pada baris yang sama, atau tab filter bila baris keluar dari filter aktif.
- Modal tidak dapat ditutup saat request Simpan Konsolidasi sedang berlangsung, agar tidak menimbulkan kesan salah bahwa penyimpanan dibatalkan. Tidak mengubah aturan backend, migrasi, Qty/UoM, atau MO/Odoo.


## Template SKU dapur + kapasitas dalam satu alur
Di **Django Admin → Production Assignments**, Admin dapat mengisi **SKU, dapur, status aktif, urutan, dan kapasitas produksi per jadwal** sekaligus dalam satu form. Excel template dapur juga mempunyai kolom `KAPASITAS_<KODE_JADWAL>`, misalnya `KAPASITAS_SUBUH` dan `KAPASITAS_PAGI`, sehingga penugasan SKU + kapasitas disimpan atomik.
Kapasitas harus angka bulat sesuai UoM master Odoo. Kolom kosong mempertahankan nilai lama (atau belum diatur untuk SKU baru); `0` adalah kapasitas nol. Kapasitas tidak diatur tetap memblokir konsolidasi pada jadwal itu. Edit/impor diaudit, dan pindah dapur untuk SKU berkapasitas memerlukan konfirmasi. Data tetap disimpan normal di `ProductCapacity(product, schedule)` karena satu SKU hanya ditugaskan ke satu dapur pada V1. Tanpa migrasi baru. Panduan: [Template SKU per Dapur](docs/TEMPLATE-PEMESANAN.md).

Menu teknis **Product Capacities** masih dapat dipakai untuk inspeksi, tetapi **read-only**; input/perubahan kapasitas harus dilakukan melalui template SKU dapur agar audit dan validasi integer konsisten.


## Simpan Draft rencana produksi (resumable)
Pada `/produksi/` → **Rencanakan**, operator kini mempunyai **Simpan Draft** selain **Simpan Konsolidasi**. Draft boleh belum memiliki tanggal/jadwal produksi atau hanya sebagian Qty SKU yang diisi. Setelah tersimpan, tutup pop-up; pada pesanan KIRIM di lingkup dapur × tanggal kirim × jadwal kirim yang sama, tombol berubah menjadi **Lanjutkan Draft**. Buka lagi untuk melanjutkan isian, termasuk setelah logout/reload/pergantian sesi.

**Penting:** Simpan Draft **tidak membuat ProductionPlan**, **tidak mengubah StoreOrder KIRIM**, **tidak menggunakan/mereservasi kapasitas**, serta tidak membuat MO/Odoo. Draft adalah data pekerjaan sementara, bukan status `ProductionPlan.DRAFT` atau `StoreOrder.DRAFT`. Form menampilkan tanggal operator terakhir dan memperingatkan jika perubahan belum disimpan sebelum menutup. Satu draft dibagikan per lingkup kirim; pembaruan dengan versi lama ditolak (409) agar dua operator tidak saling menimpa.

**Simpan Konsolidasi** tetap membutuhkan seluruh tanggal/jadwal/Qty valid, memeriksa kapasitas **terbaru** dan pesanan sumber, lalu membuat rencana+audit+status secara atomik. Draft akan dihapus dalam transaksi final yang berhasil; kegagalan finalisasi mempertahankan draft untuk diperbaiki.

Endpoint: `GET/POST /api/v1/production/consolidation/draft/` (PRODUCTION/ADMIN). **Migration `0005_production_consolidation_draft` diperlukan.** Setelah backup database dan deploy versi yang sudah di-merge, jalankan `docker compose exec api python manage.py migrate --noinput`. Lihat [Workspace Admin Produksi](docs/WORKSPACE-ADMIN-PRODUKSI.md).


## Antrean Admin Produksi sekarang berdasarkan tanggal kirim, bukan per toko
Workspace `/produksi/` menampilkan antrean **satu kelompok per tanggal kirim × dapur × jadwal kirim**, diurutkan berdasarkan tanggal kirim paling awal. Kelompok yang sama dapat memuat banyak toko; daftar utama memperlihatkan jumlah toko, pesanan final, SKU unik, serta Qty gabungan **berdasarkan UoM asli** (tidak menjumlahkan Kg dan gram/pcs menjadi satu angka). Nama toko dan Order ID dapat dibuka lewat **Lihat toko** tanpa membuat satu baris utama per toko.

Filter Semua/Kirim/Proses Produksi dan pagination 50 sekarang menghitung **kelompok pengiriman**, bukan pesanan toko. Lihat Rekap, Rencanakan, Lanjutkan Draft, dan Lihat Rencana tetap pop-up, tetapi semuanya dibuka dari lingkup kelompok yang tepat. Draft tetap tersimpan per lingkup kirim yang sama dan status pesanan KIRIM tidak berubah sampai finalisasi.

**Pengamanan pesanan susulan:** Bila satu kelompok mengandung KIRIM dan PROSES_PRODUKSI, status kelompok **Pesanan Susulan** ditampilkan. Rencana lama boleh dilihat; **tidak tersedia tombol membuat konsolidasi kedua** karena V1 belum memiliki kebijakan rekonsiliasi/alokasi pesanan terlambat. Dibutuhkan keputusan bisnis terpisah.

API baru: `GET /api/v1/production/delivery-queue/?status=ALL&page=1`. Endpoint lama `/api/v1/production/orders/` (per toko) tetap tersedia untuk kompatibilitas. Tidak ada migrasi DB baru, tidak menulis Odoo, tidak mengubah Qty/kapasitas/status. Panduan: [Admin Produksi](docs/WORKSPACE-ADMIN-PRODUKSI.md).
