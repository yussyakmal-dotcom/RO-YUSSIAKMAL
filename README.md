# RO Middleware — Django V1 bootstrap

Aplikasi input dan konsolidasi produk, bahan, produksi, dan distribusi. Odoo tetap sumber kebenaran stok dan transaksi.

Dokumentasi: [PRD](docs/PRD.md) · [DDL](docs/DDL.md) · [Django Models](docs/DJANGO-MODELS.md) · [Decision Log](docs/DECISION-LOG.md) · [Odoo Connector](docs/ODOO-CONNECTOR.md) · [Template Pemesanan](docs/TEMPLATE-PEMESANAN.md) · [Draft/Kirim](docs/ADMIN-TOKO-DRAFT-KIRIM.md) · [Frontend Admin Toko](docs/WORKSPACE-ADMIN-TOKO.md)

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

API daftar SKU aktif (perlu autentikasi): `GET /api/v1/order-templates/PST/`. Mengembalikan `id, sku, name, qty:0`. UI input Qty/Draft/Kirim React belum tersedia pada milestone ini.

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
