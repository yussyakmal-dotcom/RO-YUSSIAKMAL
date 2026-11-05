# RO Middleware — Django V1 bootstrap

Aplikasi input dan konsolidasi produk, bahan, produksi, dan distribusi. Odoo tetap sumber kebenaran stok dan transaksi.

Dokumentasi: [PRD](docs/PRD.md) · [DDL](docs/DDL.md) · [Django Models](docs/DJANGO-MODELS.md) · [Decision Log](docs/DECISION-LOG.md) · [Odoo Connector](docs/ODOO-CONNECTOR.md)

## Jalankan pengembangan lokal

```bash
cp .env.example .env
# Edit .env: ganti DJANGO_SECRET_KEY dan POSTGRES_PASSWORD
docker compose up --build -d
docker compose exec api python manage.py createsuperuser
curl http://127.0.0.1:900/health/
```

Django Admin: http://127.0.0.1:900/admin/. Service default hanya dibuka di localhost; PostgreSQL tidak diekspos ke host.

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

## Initial SKU → dapur mapping dari Product Category

Setelah master Odoo berhasil diimpor, cek pemetaan kategori ke dapur:

```bash
docker compose exec api python manage.py init_kitchen_mapping          # preview, tidak menulis
docker compose exec api python manage.py init_kitchen_mapping --apply  # mapping kosong saja
```

Periksa terlebih dahulu kategori yang belum cocok dalam preview. Mapping yang sudah ada atau diubah manual **tidak ditimpa**, termasuk saat sync Odoo berikutnya. Kategori Paket diarahkan ke Packing (PCK). Tidak diperlukan migration baru. Lihat [panduan mapping awal](docs/ODOO-CONNECTOR.md#initial-mapping-sku--dapur-dari-product-category).

Schema dieksekusi melalui Django migrations. Jangan jalankan SQL docs/DDL.md secara manual. Proyek ini *scaffold development*, belum memiliki seluruh workflow operasional, integrasi transaksi Odoo, atau deployment production.

Jangan commit .env, credential Odoo, file backup. Hindari `docker compose down -v` jika data PostgreSQL ingin dipertahankan.
