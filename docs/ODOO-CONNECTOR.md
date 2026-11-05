# Odoo 19 JSON-2 — Connector Read-Only (V1)
**Status:** implementasi konektor master awal; belum terhubung ke database Odoo milik pengguna dan belum divalidasi terhadap field tenant yang sebenarnya.

## Tujuan dan pembatasan
Connector hanya memanggil **POST `/json/2/<model>/search_read`** untuk **membaca** data dari Odoo. Tidak ada pemanggilan `create`, `write`, `unlink`, `action_*`, konfirmasi MO, atau transfer di Odoo.

Lima model yang diizinkan:
- `stock.warehouse` — code, name, lot_stock_id
- `stock.location` — id dan complete_name untuk 19 lokasi RO yang disepakati
- `product.product` — id, default_code, name, category, UoM, product_tmpl_id
- `mrp.bom` — BoM normal, product/product template, output BoM
- `mrp.bom.line` — komponen langsung dan quantity BoM

Semua pembacaan dilakukan **sebelum** perubahan lokal. Jika satu request gagal, perintah berhenti dan **tidak melakukan penulisan** PostgreSQL middleware.

## Persiapan di Odoo
1. Pastikan paket Odoo SaaS memiliki akses External API (**Custom plan** menurut dokumentasi Odoo 19).
2. Siapkan akun **bot read-only** khusus; beri hak *read* model/record yang diperlukan, tidak perlu izin create/write.
3. Buat API key untuk akun bot. **Jangan kirim API key atau isi file .env ke chat/GitHub.**
4. Periksa model dan field khusus tenant di halaman `https://<domain-odoo>/doc` jika terjadi HTTP 4xx/5xx.

Referensi resmi: https://www.odoo.com/documentation/19.0/developer/reference/external_api.html

## Konfigurasi di server Debian
Tambahkan ke **.env yang sudah ada** (jangan menimpa file .env dengan salinan example):

```dotenv
ODOO_BASE_URL=https://nama-perusahaan.odoo.com
ODOO_DATABASE=nama_database_atau_kosong_jika_tidak_diperlukan
ODOO_API_KEY=api_key_dari_akun_bot
```

`ODOO_BASE_URL` harus HTTPS root domain Odoo, tanpa `/web` atau `/json/2`. `ODOO_DATABASE` boleh dikosongkan jika routing domain Odoo sudah menentukan database.

Lalu jalankan dari root repository:

```bash
git pull origin main
nano .env
docker compose up -d --build --force-recreate api
docker compose exec api python manage.py odoo_probe
```

## Preview dan sinkronisasi
**Preview tidak mengubah database manapun:**

```bash
docker compose exec api python manage.py odoo_sync_master
```

Output berisi jumlah warehouse yang cocok dari 19 kode RO, lokasi yang cocok, jumlah produk/BoM, daftar kode/lokasi yang belum ditemukan, dan contoh SKU dengan lebih dari satu kandidat BoM.

Jika output sudah benar, sinkronkan **hanya database lokal middleware**:

```bash
docker compose exec api python manage.py odoo_sync_master --apply
```

Import boleh diulang: data master dicocokkan dengan **Odoo ID**. Tidak ada transfer atau MO yang dibuat. Sinkronisasi ini tidak menandai produk yang hilang dari Odoo sebagai nonaktif, dan **tidak menghapus apa pun**.

## Aturan keamanan dan data
- **Mapping SKU → dapur aktif adalah milik middleware.** Tabel `ProductionAssignment` tidak pernah ditulis oleh sync ini. Initial import mapping masih menunggu konfirmasi field asal di Odoo.
- Lokasi disesuaikan **hanya** bila `complete_name` cocok dengan 19 nama lokasi yang sudah disetujui. Lokasi yang tidak cocok dilaporkan, tidak ditebak dari `lot_stock_id`.
- Untuk BoM, BoM spesifik varian lebih diprioritaskan daripada BoM template generik. Jika lebih dari satu kandidat, cache BoM produk tersebut **tidak ditimpa** dan SKU dilaporkan ambigu.
- BoM `phantom` (kit) tidak dianggap sebagai BoM manufaktur untuk pembuatan MO. Status tipe BoM PAKET di tenant perlu dicek.
- Produk tanpa BoM yang cocok mendapatkan cache BoM kosong. Cache komponen mencakup **komponen langsung**, tidak membuat MO subproduk.
- Tidak mengambil stok live dulu. Kebutuhan bahan dan alokasi Packing akan menggunakan pembacaan stok Odoo pada tahap integrasi berikutnya.
- Saat implementasi masih tahap development, **port host tetap 900**. Tidak ada endpoint web untuk menjalankan sync; perintah hanya dijalankan oleh operator di shell server.
- Gunakan akses API key dengan prinsip hak minimum dan rotasi; setiap penggunaan API key dicatat oleh Odoo sesuai izin akun.

## Initial mapping SKU → dapur dari Product Category

Pengguna memastikan bahwa **Product Category** pada daftar Products Odoo adalah penentu dapur awal. Screenshot menampilkan kategori `Legit`, `Paket`, dan `Pastry`. Kategori tersebut sudah dibaca menjadi field `Product.category` middleware melalui `categ_id`. Tidak perlu memanggil API tambahan atau mengubah skema database.

Perintah aman untuk dijalankan pada server yang sudah mengimpor master:

```bash
git pull origin main
docker compose exec api python manage.py init_kitchen_mapping
```

Preview menunjukkan jumlah SKU kandidat, kategori yang dikenali dan belum cocok, mapping lama, serta warehouse yang belum tersedia. Periksa hasilnya dahulu; **tidak ada perubahan** pada mode preview.

Kandidat mapping berdasarkan **nama kategori persis** (perbedaan kapital/spasi diabaikan), tanpa tebakan dari nama produk, BoM, kode SKU, atau nama kategori bertingkat:

| Category Odoo (nama tepat) | Warehouse middleware |
|---|---|
| Asin | ASN |
| Cake Slice | CKS |
| Gorengan | GRG |
| Jajan Pasar | JP |
| Pastry | PST |
| Roti | ROTI |
| Sultan & Lemper | SUL |
| Tart | TART |
| Premik | PREMI |
| Legit | LEGIT |
| Paket | PCK (Packing) |

**Catatan:** kategori selain Legit, Paket, dan Pastry pada tabel di atas adalah **kandidat konvensi nama berdasarkan daftar dapur**, bukan kategori yang sudah terbukti ada di tenant Odoo. Preview memberi verifikasi realnya. Nama kategori seperti `Bahan Baku`, `WIP`, `Premix`, atau nested path `Raw Materials / Pastry` tidak dipetakan otomatis. Ini menghindari keliru menempatkan bahan baku sebagai produk jadi.

Jika preview sudah sesuai:

```bash
docker compose exec api python manage.py init_kitchen_mapping --apply
```

`--apply` hanya membuat record `ProductionAssignment` yang **belum ada** di PostgreSQL lokal. Tidak ada perubahan di Odoo, tidak ada perubahan mapping SKU yang sudah dimodifikasi manual. Menjalankannya kembali tidak menghasilkan duplikasi. Setelahnya, ubah pemindahan dapur melalui pengelolaan middleware/Django Admin (sementara), bukan dengan sinkronisasi rutin.

## Belum diselesaikan
- Variasi nama kategori produksi lain di tenant yang tidak cocok persis, serta kategori WIP/Premix; preview harus direview.
- Nama field/customisasi BoM atau product category tenant (periksa /doc).
- Stok usable vs reserved, UoM conversion, dan integrasi Draft MO/Transfer.
- Produk Odoo archived tidak dihapus/dinonaktifkan secara otomatis oleh sync ini.
- Tenant nyata belum diuji; hasil tests menggunakan respons Odoo tiruan.

## Verifikasi tenant nyata — 2026-11-05

Pengguna telah menjalankan perintah berikut di server Debian dan melaporkan hasilnya dalam percakapan proyek:

- `python manage.py odoo_probe`: koneksi JSON-2 **berhasil** dengan akun read-only; contoh warehouse `T_SD`.
- `python manage.py odoo_sync_master --apply`: **berhasil** menyimpan master di PostgreSQL middleware.
- Warehouse ditemukan: **19**, missing **0**.
- Stock location cocok: **19**, missing **0**.
- Produk dibaca: **2.553**.
- BoM dibaca: **957**.
- Produk dengan kandidat BoM ambigu: **0**.

**Batas interpretasi hasil:** angka 957 adalah jumlah record BoM yang dibaca, **bukan** bukti semua SKU punya BoM ataupun setiap SKU telah dipetakan ke dapur. Sinkronisasi rutin ini tidak memodifikasi `ProductionAssignment`. Sumber data untuk initial mapping SKU → dapur belum dikonfirmasi. Read-only connector terverifikasi pada tenant nyata untuk probe dan master import, belum untuk stok live/transaksi MO/DO.
