# Decision Log dan Jejak Percakapan — RO Middleware
**Versi:** 0.1 · **Disusun:** 2026-11-05 · **Cakupan:** keseluruhan percakapan desain yang tersedia hingga permintaan PRD/DDL.  
**Metode:** rekonstruksi keputusan **dari transcript percakapan**, bukan salinan verbatim setiap pesan. Urutan bernomor mengikuti urutan topik dalam dialog; kutipan singkat adalah parafrasa. Perubahan/penyempurnaan terbaru mengesampingkan dugaan lama.  
**Legenda:** ✅ Diputuskan oleh pengguna; 🟡 usulan/interpretasi yang perlu validasi; ❓ terbuka.

## Kronologi keputusan eksplisit
| ID | Status | Peristiwa/keputusan dari percakapan | Dampak |
|---|---|---|---|
| D-001 | ✅ | Middleware mengonsolidasi permintaan toko lalu mengoordinasikan produksi, bahan baku, transfer, packing dan distribusi lewat Odoo 19 SaaS | Integrasi ERP, bukan inventory sendiri |
| D-002 | ✅ | Diberikan daftar 19 warehouse dan lokasi: 1 Central, 10 dapur, 1 Packing, 7 toko | Master warehouse baseline |
| D-003 | ✅ | Setiap produk punya satu dapur produksi aktif; bisa dipindah sesuai SOP, bukan produksi paralel | Mapping tunggal SKU→dapur |
| D-004 | ✅ | Perpindahan dapur dan transfer WIP antar-dapur diatur SOP; middleware tak perlu orkestrasi bentrok | Hindari fitur penjadwalan transfer WIP |
| D-005 | ✅ | Central menerima bahan baku dari supplier dan menyuplai gudang dapur; hasil produksi ke Packing untuk toko | Alur logistik utama |
| D-006 | ✅ | Premix dibuat di Central (campur menjadi SKU), WIP dibuat di dapur (proses fisik), WIP tinggal di dapur sampai dipindah | Dua pola replenishment |
| D-007 | ✅ | Premix/WIP diproduksi berdasarkan stok minimum masing-masing warehouse, bukan efek MO produk jadi | Per-SKU/per-warehouse minima |
| D-008 | ✅ | Tidak ada BoM dalam BoM yang memicu MO; di Odoo juga sudah dikonfigurasi tidak ada BoM memicu BoM | Tanpa recursive manufacturing trigger |
| D-009 | ✅ | MO produk jadi konsolidasi seluruh toko per produk dan dapur | Agregasi demand |
| D-010 | ✅ | Tiga tanggal penting: pesan, produksi, kirim; tiga jadwal produksi standar dan dapat ditambah | Master schedule dan tanggal terpisah |
| D-011 | ✅ | Kirim subuh mengikuti produksi malam-subuh; kirim pagi ±08 mengikuti subuh-08; kirim siang mengikuti 08-10 | Mapping jadwal kirim→produksi |
| D-012 | ✅ | Permintaan bahan dari dapur ke Central dikonsolidasi per jadwal produksi dan **hanya kekurangan** setelah stok dapur | Net requirements |
| D-013 | ✅ | Admin Produksi boleh menambah Qty permintaan bahan untuk buffer melebihi minimum | Simpan minimum dan buffer terpisah |
| D-014 | ✅ | Kapasitas produksi ada per SKU per jadwal | Kapasitas sebagai batas |
| D-015 | ✅ | Output BoM adalah kelipatan produksi; contoh 100, permintaan 210→300 | Round-up batch |
| D-016 | ✅ | Pembulatan tidak boleh melampaui kapasitas; SOP telah mengatur nilai kapasitas dengan memperhitungkan kelipatan | Validasi qty_mo ≤ kapasitas |
| D-017 | ✅ | Toko input Qty melalui katalog SKU per dapur, satu dapur bisa 50–700 SKU; status Draft dapat diedit, Kirim terkunci | Bulk-input UI |
| D-018 | ✅ | Toko mengirim per dapur terpisah | State per toko-dapur-jadwal |
| D-019 | ✅ | Saat Draft→Kirim item Qty 0 dihapus; **Qty ≥1 valid** | Filter submit |
| D-020 | ✅ | Pada pukul 07.00 WIB H-2, Draft otomatis menjadi Kirim; bila semua nol, No Order yang normal (toko libur) | Scheduled submit |
| D-021 | ✅ | Admin Produksi hanya mengonsolidasi status Kirim, dan bisa merevisi hingga MO dibuat | Revisable plan |
| D-022 | ✅ | Admin Produksi bisa ubah Qty produksi, tetap mengikuti pembulatan/kapasitas | Human-in-control |
| D-023 | ✅ | Simpan Qty permintaan asli, Qty rencana revisi, Qty MO terpisah, audit perubahan otomatis | Traceability |
| D-024 | ✅ | Admin Packing memutuskan pembagian kurang/lebih per toko tanpa mengubah order asli | Allocation terpisah |
| D-025 | ✅ | Packing tidak mempunyai stok sisa; seluruh hasil produksi yang masuk Packing harus didistribusi hari itu | Same-day allocation |
| D-026 | ✅ | Produk aktual dapat kurang/lebih dari MO karena rusak/ukuran; transfer aktual tak harus sama rencana | Target ≠ actual |
| D-027 | ✅ | Kebutuhan bahan diselesaikan dulu sebelum middleware membuat MO dan transfer di Odoo | Gate sebelum API |
| D-028 | ✅ | Middleware V1 hanya membuat **Draft MO dan Draft Stock Transfer**; tidak menjalankan/confirm | Batas otomasi V1 |
| D-029 | ✅ | Kategori SKU PAKET memiliki BoM di Odoo; toko memesan PAKET; MO Draft untuk perakitan di PCK/Packing | Paket bagian proses produksi |
| D-030 | ✅ | Di Packing, perakitan Paket prioritas lebih tinggi dari pengiriman produk satuan; shortfall satuan dapat diterima | Priority allocation |
| D-031 | ✅ | Tujuan middleware terutama mempercepat/menyederhanakan input; dashboard sekunder | Minimal operational workflow |
| D-032 | ✅ | Ada empat workspace: Toko, Produksi, Packing, Administrator | RBAC/UX |
| D-033 | ✅ | Administrator dapat memakai seluruh workspace dan semua aksi untuk QA, tanpa menjadi operator harian | Superuser audit |
| D-034 | ✅ | Odoo→middleware: SKU, BoM, warehouse, location, stok; middleware: mapping dapur, kapasitas, jadwal, minima dan order | Data ownership |
| D-035 | ✅ | Mapping SKU→dapur diimpor dari Odoo **sekali awal**, perubahan setelahnya hanya di middleware | No overwrite |
| D-036 | ✅ | Field Source Document dibangkitkan middleware: kode warehouse tanpa suffix /Stock, `YYMMDD`, counter mulai 10001 | Standard reference |
| D-037 | ✅ | Counter reset **harian per warehouse**; tanggal yang dipakai adalah tanggal **pembuatan dokumen**, WIB | Sequence invariant |
| D-038 | ✅ | PostgreSQL dalam Docker dipilih; frontend merujuk visual SAP (diterjemahkan sebagai Fiori/Horizon) | Stack/design direction |
| D-039 | 🟡 | Django+DRF, React+TypeScript/Vite, Redis/Celery dan Docker Compose direkomendasikan asisten; belum ada persetujuan eksplisit stack menyeluruh | Tech recommendation |
| D-040 | ✅ | Kode & dokumentasi akan disimpan di repository GitHub `yussyakmal-dotcom/RO-YUSSIAKMAL` | Repo source of truth |

## Hal terbuka / pertanyaan tanpa jawaban final
| ID | Status | Pertanyaan |
|---|---|---|
| O-001 | ❓ | Ketika hasil pembulatan melewati kapasitas, apakah Admin menurunkan rencana, membatasi Qty, atau membagi ke jadwal lain? Tidak boleh diam-diam melebihi kapasitas. |
| O-002 | ❓ | Tanggal administratif produksi untuk shift melintasi tengah malam tanggal sebelumnya atau tanggal kirim? |
| O-003 | ❓ | Kebutuhan komponen Paket ditambahkan otomatis ke permintaan produksi dapur atau hanya informasi planning? Prioritas di Packing sudah pasti. |
| O-004 | ❓ | Apakah DO toko cukup Draft atau langsung Confirm di V1? |
| O-005 | ❓ | Transfer dari dapur ke Packing dibuat middleware atau proses Odoo setelah manufaktur, serta status awalnya? |
| O-006 | ❓ | Trigger/approval dan target produksi replenishment Premix/WIP per warehouse yang minimum tidak tercapai. |
| O-007 | ❓ | Source Document untuk dokumen antargudang memakai kode asal atau kode tujuan? Contoh format dan reset telah final. |
| O-008 | ❓ | Pada stok, gunakan available/free vs on-hand, reservasi Odoo, transfer masuk/keluar yang belum selesai dan satuan UoM. |
| O-009 | ❓ | Jadwal tambahan dibuat oleh siapa, aturannya per toko/per dapur, dan bagaimana mapping delivery/production date? |
| O-010 | ❓ | Infrastruktur hosting, backup cadence dan strategi pemisahan QA vs production. |
| O-011 | ❓ | Teknologi backend/frontend yang disarankan asisten perlu pengesahan eksplisit jika dijadikan baseline wajib. |

## Koreksi penting selama percakapan
- Qty valid adalah **≥1**, bukan >1.
- Toko dapat mengirim **per dapur secara independen**, bukan satu kirim semua dapur.
- Gudang Packing **tidak membawa sisa stok** ke hari berikutnya.
- Kapasitas sudah disiapkan oleh SOP untuk kelipatan; sistem tetap menolak qty_mo > kapasitas.
- Admin Produksi dapat **mengubah** Qty rencana; Admin Packing yang memutuskan alokasi kekurangan.
- BoM Paket dibaca dari Odoo dan **tidak otomatis memicu** MO komponen.
- Penomoran tanggal source document berdasar **tanggal dokumen dibuat**, bukan produksi/kirim.

## Protokol memperbarui dokumen berikutnya (usulan)
1. Setiap keputusan baru mendapatkan ID `D-041` dan seterusnya, dicatat berdasarkan **pernyataan persetujuan pengguna**, bukan dugaan asisten.
2. Jika keputusan direvisi, tandai superseded dan cantumkan keputusan penggantinya.
3. Sinkronkan PRD, DDL, dan acceptance tests pada pull request yang sama; hindari perubahan aturan diam-diam.
4. Catatan transcript ini **ringkasan kronologis terstruktur**, bukan export verbatim chat; gunakan sebagai decision trace yang dapat diaudit secara manual.

## Referensi
- [PRD](./PRD.md)
- [DDL](./DDL.md)
- Repository: https://github.com/yussyakmal-dotcom/RO-YUSSIAKMAL


## Pembaruan 2026-11-05 — Finalisasi skema ringan
- **D-041 (✅):** Pengguna meminta finalisasi DDL dan rancangan model Django dengan pendekatan pragmatis: **jangan terlalu ketat, bukan super app**.
- **T-001 (🟡 implementasi disarankan):** Django ORM + migrations menjadi satu-satunya sumber kebenaran untuk skema riil. DDL tetap dokumentasi referensi.
- **T-002 (🟡 implementasi disarankan):** Gunakan Django built-in auth/Groups, cache komponen BoM dalam JSONB, audit sederhana, dan outbox minimal; tidak membuat workflow engine generik ataupun ledger stok sendiri.
- Dokumentasi terkait: [DDL Lean](./DDL.md) dan [Django Models](./DJANGO-MODELS.md).
- Keputusan bisnis sebelumnya tetap berlaku; beberapa detail integrasi Odoo, DO, dan kebutuhan Paket masih terbuka.

## Implementasi berikutnya — Bootstrap backend V1
- **I-001 (✅ sudah dikerjakan):** Baseline project Django, PostgreSQL 16 via Docker Compose, Django ORM dan `0001_initial` migration telah ditambahkan di repository.
- **I-002 (✅ validasi otomatis):** GitHub Actions lulus pemeriksaan Django, `makemigrations --check --dry-run`, `migrate` di PostgreSQL dan empat tes sederhana. PR #1 di-merge ke `main`.
- **I-003 (batasan):** `compose.yaml` saat ini hanya untuk pengembangan lokal; belum ada API Odoo, form React, jadwal auto-submit, layanan Celery, atau deployment production.
- **I-004 (prinsip):** Tetap satu monolith Django dan PostgreSQL; tambah worker/Redis hanya saat pekerjaan integrasi/jadwal diimplementasikan. Tidak membuat stok atau ERP kedua.

Lihat [README](../README.md) dan [initial migration](../backend/ro_core/migrations/0001_initial.py).

## Implementasi berikutnya — Odoo connector read-only
- **I-005 (✅ implementasi kode):** Dibuat client JSON-2 yang hanya mengizinkan `search_read` pada lima model master Odoo, perintah `odoo_probe` dan `odoo_sync_master` dengan preview default.
- **I-006 (✅ prinsip keamanan):** Opsi `--apply` hanya memperbarui PostgreSQL middleware setelah semua data Odoo selesai dibaca; tidak melakukan write ke Odoo, tidak menyentuh `ProductionAssignment` dan tidak menebak warehouse/location yang tidak cocok.
- **I-007 (❓ tenant validation):** Model/field API di Odoo 19 sebenarnya, tipe BoM Paket, dan sumber awal mapping SKU→dapur tetap harus diverifikasi menggunakan /doc Odoo serta akses bot read-only.
- **I-008 (🚧 status):** Pengujian unit CI memakai data tiruan; koneksi tenant Odoo belum dilakukan dan membutuhkan pengaturan rahasia hanya di .env server lokal.
- Petunjuk: [Odoo Connector](./ODOO-CONNECTOR.md).
