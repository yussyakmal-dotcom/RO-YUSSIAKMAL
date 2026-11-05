# RO Middleware — Django V1 bootstrap

Aplikasi input dan konsolidasi produk, bahan, produksi, dan distribusi. Odoo tetap sumber kebenaran stok dan transaksi.

Dokumentasi: [PRD](docs/PRD.md) · [DDL](docs/DDL.md) · [Django Models](docs/DJANGO-MODELS.md) · [Decision Log](docs/DECISION-LOG.md)

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

Schema dieksekusi melalui Django migrations. Jangan jalankan SQL docs/DDL.md secara manual. Proyek ini *scaffold development*, belum memiliki implementasi seluruh workflow, integrasi Odoo atau deployment production.

Jangan commit .env, credential Odoo, file backup. Hindari `docker compose down -v` jika data PostgreSQL ingin dipertahankan.
