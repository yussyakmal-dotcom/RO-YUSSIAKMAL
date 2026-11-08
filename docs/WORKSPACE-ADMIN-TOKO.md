# Workspace Admin Toko — React V1 (SAP Fiori Horizon-inspired)
**Tanggal:** 2026-11-05  
**Status:** implementasi UI untuk pengujian lokal. Belum deployment produksi.

## Hasil yang bisa dicoba
Aplikasi React + TypeScript + Vite sekarang disajikan **langsung oleh Django di port 900**:
- `http://localhost:900/` → mengarahkan ke `/toko/`.
- `http://localhost:900/toko/` → login dan Workspace Admin Toko.
- `http://localhost:900/admin/` → Django Admin seperti sebelumnya.

Tidak perlu port web 5173 untuk pemakaian normal. Docker memakai **multi-stage build** (Node hanya membangun asset frontend, Python menjalankan backend). Port internal Django tetap 8000, host port **900**.

## Cara menjalankan di server Debian

```bash
cd ~/RO-YUSSIAKMAL
git pull origin main
docker compose up -d --build --force-recreate api
docker compose exec api python manage.py seed_order_schedules
docker compose exec api python manage.py check
curl http://localhost:900/health/
```

**Catatan:** kini `compose.yaml` tidak memasang bind mount `./backend:/app` lagi agar build React tidak tertimpa. Edit kode backend memerlukan `docker compose up -d --build --force-recreate api` untuk diterapkan. Data PostgreSQL tetap pada volume `postgres_data`, tidak dihapus.

## Login pengguna
Gunakan akun **superuser Django** yang sudah dibuat untuk uji pertama. Akun Admin Toko biasa harus:
1. Tersimpan di Django Admin → Users.
2. Tergabung dalam Django Group **STORE**.
3. Memiliki entri **User Warehouse Access** yang menghubungkan akun dengan toko yang boleh dikelola.

Akun dengan Group **ADMIN** atau `is_superuser` dapat memilih semua toko untuk QA. Tindakan pada Draft/Kirim dicatat menggunakan akun yang benar-benar login.

Login dilakukan di `/toko/`, tidak harus melalui Django Admin. Autentikasi menggunakan **Django Session + CSRF** di domain/port yang sama.

## Alur pemesanan
1. Pilih **Toko** yang berhak diakses.
2. Pilih **Dapur / Template** (akan menampilkan jumlah SKU aktif dari template manual; mis. Dapur Jajan Pasar).
3. Pilih **Tanggal Pengiriman** (default tampilan H+2 berdasarkan Asia/Jakarta, bebas diubah) dan **Jadwal Kirim**.
4. Tabel SKU/ID dan Nama Produk otomatis muncul dari template. Pengguna cukup mengisi **Qty bilangan bulat** (0, 1, 2, ...), tanpa desimal; gunakan Tab atau Enter untuk pindah.
5. Tombol **Simpan Draft** menyimpan Qty. Formulir bisa ditutup/dibuka ulang dan Qty lama tetap ada/editable.
6. Tombol **Kirim Pesanan** meminta konfirmasi, menyimpan perubahan terbaru bila belum disimpan, dan mengirim hanya baris Qty **≥ 1**. Status berubah menjadi `KIRIM` dan form terkunci.
7. Jika semuanya 0, kirim menjadi **NO_ORDER**, bukan error. Qty pecahan ditolak saat input/simpan Draft.

Ada pencarian SKU/nama, filter `Hanya Qty ≥ 1`, ringkasan jumlah SKU dan Qty, serta peringatan saat berpindah pilihan dengan Draft yang belum tersimpan. SKU nonaktif dari template tidak muncul pada order baru; jika sudah ada dalam Draft sebelum dinonaktifkan, tetap muncul untuk diperiksa dan dikoreksi tanpa kehilangan data.

### Peringatan saat menutup tab atau memuat ulang
- Jika Qty telah diubah dan belum berhasil disimpan, aplikasi meminta browser menampilkan konfirmasi saat tab ditutup, halaman dimuat ulang, atau pengguna meninggalkan halaman. Pengguna dapat membatalkan untuk melanjutkan pengisian dan menyimpan Draft.
- Perlindungan tetap aktif selama penyimpanan berlangsung atau bila simpan gagal. Setelah Simpan Draft atau Kirim berhasil, peringatan berhenti; perubahan Qty berikutnya mengaktifkannya kembali.
- Dialog dan teks konfirmasi mengikuti browser, dan sebagian browser/perangkat tidak selalu menampilkannya. Ini bukan penyimpanan otomatis atau pemulihan offline; tetap gunakan **Simpan Draft** sebelum meninggalkan halaman.

## Endpoint yang digunakan
- `GET /api/v1/auth/csrf/` — set cookie CSRF.
- `POST /api/v1/auth/login/` — login sesi.
- `GET /api/v1/auth/me/` — identitas + toko, dapur, jadwal tersedia.
- `POST /api/v1/auth/logout/` — logout sesi.
- `GET /api/v1/store-orders/?...` — buka Draft / order readonly.
- `POST /api/v1/store-orders/` — simpan Draft.
- `POST /api/v1/store-orders/<id>/send/` — Kirim, tanpa retry otomatis jika kegagalan tidak pasti.

Hanya koneksi ke middleware; **tidak ada transaksi write ke Odoo** pada workspace ini.

## Desain UI
- Kontrol **Teks − / +** di kanan atas mengubah semua ukuran font sebesar **1 poin per klik**, termasuk tabel dan modal. Pengaturan berlaku bersama untuk Workspace Toko/Produksi dan halaman login, disimpan pada browser yang sama, dengan rentang penyesuaian −2 sampai +10 poin dari ukuran awal.
- Mengacu estetika SAP Fiori Horizon (light, komponen enterprise, tabel compact), **bukan** SAPUI5 atau menyalin aset SAP.
- Tabel Qty bergaya spreadsheet dengan header sticky, pencarian SKU/nama, keyboard input; menggunakan `memo` per baris untuk mengurangi render ulang saat mengedit 50–700 SKU.
- Responsive untuk laptop, desktop, dan perangkat berlayar kecil.
- **Frontend dibangun dari source** di `frontend/`; keluaran build disalin ke Django template dan static dir di image Docker.

## Ruang lingkup / batasan
- **Auto-submit H-2 07.00 WIB telah diimplementasikan pada backend dan tersedia contoh systemd timer**, tetapi timer **belum diaktifkan di server**. Input Draft setelah cutoff dan recovery downtime belum diputuskan. Lihat [panduan](./AUTO-SUBMIT-H-2.md).
- Belum ada konsolidasi MO dan transfer ke Odoo dari frontend ini.
- Django runserver + staticfiles saat ini **hanya untuk development lokal**; sebelum akses publik/production perlu reverse proxy, HTTPS, static server dan service WSGI yang sesuai.
- Daftar jadwal dibuat sekali dengan `seed_order_schedules` jika belum ada; perintah tidak mengganti konfigurasi jadwal yang telah dimodifikasi.
- Frontend belum menyimpan data secara offline. Jika koneksi terputus sebelum Draft disimpan, input yang belum disimpan bisa hilang.

## Validasi Qty integer
- Field input Qty menggunakan keyboard angka dan hanya menerima digit `0-9`. Minus, koma, titik desimal, dan notasi `e` tidak diterima.
- API tetap memvalidasi agar klien lain tidak bisa mengirim Qty pecahan. Contoh `1` diterima, `1.5` ditolak dengan HTTP 400.
- Qty desimal dari Draft versi lama ditampilkan untuk dikoreksi manual sebelum Kirim; middleware **tidak membulatkan otomatis**.
- Nilai Qty disimpan pada skema lama Decimal(18,4); perubahan ini **tidak membutuhkan migration DB** dan tidak memengaruhi perhitungan bahan baku.

## Label auto-submit pada Workspace Toko
Setelah suatu Draft difinalisasi oleh perintah H-2, GET pesanan mengembalikan `auto_submitted=true`. Header order menampilkan **Terkirim otomatis** atau **No Order otomatis** dan seluruh Qty terkunci. Kode backend/timer hanya dijalankan setelah administrator mengaktifkan service pada Debian sesuai [panduan Auto-submit](./AUTO-SUBMIT-H-2.md).
