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
| D-035 | 🟡 | Mapping aktif SKU→dapur dimiliki middleware; metode impor/pengisian awal perlu ditetapkan dan tidak boleh menimpa perubahan manual | No overwrite |
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

## Validasi operasional — 2026-11-05
- **I-009 (✅ tenant nyata):** Pengguna menjalankan `odoo_probe` dan `odoo_sync_master --apply` pada server Debian; koneksi Odoo 19 JSON-2 berhasil.
- Hasil nyata: **19/19 warehouse**, **19/19 lokasi**, **2.553 produk**, **957 record BoM**, **0 kandidat BoM ambigu**; master berhasil disimpan di PostgreSQL middleware.
- **I-010 (❓ tahapan berikutnya):** Initial mapping SKU→dapur belum terisi/dikonfirmasi oleh hasil impor ini; perlu menentukan sumber mapping di Odoo sebelum Workspace Admin Toko memfilter katalog per dapur.
- Tidak ada bukti dalam hasil ini bahwa 957 BoM mewakili seluruh SKU, stok live sudah sinkron, atau API transaksi MO/DO sudah siap.
- Lihat [hasil verifikasi connector](./ODOO-CONNECTOR.md#verifikasi-tenant-nyata--2026-11-05).

## Konfirmasi sumber mapping dapur — 2026-11-05
- **D-042 (❌ SUPERSEDED oleh D-043):** Pada awalnya ditafsirkan bahwa kategori produk Odoo menentukan dapur. Ini **keliru** dan telah dikoreksi pengguna: Product Category hanya pengelompokan.
- **I-011 (❌ DIBATALKAN):** Perintah `init_kitchen_mapping` berbasis Product Category pernah dibuat, lalu dinonaktifkan. Tidak boleh digunakan untuk membuat mapping.
- **I-012 (❌ DIBATALKAN):** Tebakan dapur dari nama kategori tidak digunakan.
- **I-010 diperjelas lagi oleh D-043:** Metode initial assignment SKU belum disepakati; Odoo menentukan tempat produksi per MO menggunakan Operation Type.
- PRD dan [panduan connector](./ODOO-CONNECTOR.md#verifikasi-manufacturing-operation-type) diperbaiki setelah koreksi.

## Koreksi operasional — Operation Type pada MO (2026-11-05)
- **D-043 (✅ KEPUTUSAN TERKINI):** Pengguna menegaskan penentuan dapur **saat pembuatan MO** didasarkan pada **Manufacturing Operation Type** Odoo, bukan Product Category. Dalam API Odoo direpresentasikan oleh `mrp.production.picking_type_id`, yang mengacu `stock.picking.type`.
- **D-044 (✅ keselamatan perubahan):** Pemetaan kategori otomatis merupakan salah tafsir; prosedur `init_kitchen_mapping` dinonaktifkan dan kode kategori dihapus. Tidak ada pengubahan mapping yang sudah tersimpan secara otomatis.
- **I-013 (✅ implementasi diagnostik):** Perintah `odoo_mo_operation_types` hanya membaca daftar operation types manufaktur yang terkait warehouse Odoo, sebagai dasar konfigurasi mapping eksplisit ke dapur.
- **O-012 (❓ terbuka):** Bagaimana aturan *default kitchen* untuk daftar pesanan toko ditentukan ketika produk belum mempunyai MO—dipilih admin secara manual atau diturunkan dari referensi MO historis? Penentuan lokasi pada MO sendiri tetap dari Operation Type.
- **O-013 (❓ terbuka):** Pastikan ID Operation Type 10 dapur dan Packing, terutama operasi perakitan PAKET, sesuai konfigurasi Odoo tenant sebelum middleware membuat Draft MO.

## Keputusan terbaru — Template pemesanan manual per dapur (2026-11-05)
- **D-045 (✅):** Pengguna menetapkan *mapping/daftar SKU yang boleh dipesan* dikelola **manual**, misalnya SKU Dapur Pastry diupload lewat Excel dan dirawat di middleware. Ini menggantikan asumsi initial assignment otomatis via Product Category.
- **D-046 (✅):** Setiap SKU pada template dapur memiliki flag **Aktif/Nonaktif**; SKU nonaktif tidak ditampilkan di formulir toko.
- **D-047 (✅):** Saat Admin Toko memilih dapur, middleware otomatis memuat template dapur sebagai daftar **ID/SKU, nama, Qty**. Admin Toko hanya mengisi Qty, tidak memilih/memasukkan SKU satu per satu.
- **D-048 (✅):** Product Category Odoo bukan penentu dapur. Penentuan operasi saat membuat MO tetap memakai **Operation Type** Odoo seperti D-043. Katalog pemesanan dan routing MO adalah dua konsep berbeda.
- **I-014 (pilihan implementasi V1):** Tidak menambah tabel template header. `ProductionAssignment` yang sudah ada digunakan sebagai satu penugasan SKU→dapur, dengan `is_active` dan `sort_order` (migration 0002). Daftar template untuk satu dapur dapat dibaca langsung dari assignment aktif.
- **I-015 (implementasi awal):** Django Admin mendukung unduh format Excel, preview upload, impor Excel, edit mapping/manual, dan API read-only daftar SKU untuk frontend. Toko Draft/Kirim dan React UI belum dibangun.
- **I-016 (aturan impor aman):** Tidak menimpa master Odoo, tidak menghapus SKU yang absen dari Excel berikutnya, melarang assignment lintas dapur secara diam-diam, dan mencatat audit perubahan.
- Referensi: [Template Pemesanan per Dapur](./TEMPLATE-PEMESANAN.md).

## Penegasan Draft / Kirim oleh pengguna (2026-11-05)
- **D-049 (✅):** Saat **Simpan Draft**, pesanan masih dapat dibuka lagi untuk mengedit Qty. Draft tidak sama dengan Kirim dan belum masuk konsolidasi produksi.
- **D-050 (✅):** Saat **Kirim**, hanya baris dengan Qty **≥1** yang diproses; Qty di bawah 1 dikeluarkan. KIRIM mengunci penyuntingan Admin Toko.
- **I-017 (implementasi API):** Endpoint Django untuk membaca Draft/daftar SKU, menyimpan ulang Draft, dan Kirim dengan transaksi atomik/row lock. Jika tidak ada baris Qty ≥1, status `NO_ORDER` sesuai keputusan sebelumnya.
- **I-018 (batas milestone):** Frontend React dan penjadwal auto-submit H-2 07.00 WIB belum diimplementasikan; API menangani Kirim manual terlebih dahulu.
- Referensi: [Aturan API Draft/Kirim](./ADMIN-TOKO-DRAFT-KIRIM.md).

## Implementasi frontend Admin Toko — 2026-11-05
- **I-019 (implementasi):** React + TypeScript + Vite dengan tampilan enterprise light terinspirasi SAP Fiori Horizon untuk Workspace Admin Toko.
- **I-020 (implementasi):** Django melayani frontend di `/toko/` pada **port host 900 yang sama**; Django Admin tetap di `/admin/`. Docker multi-stage membangun asset React dan menyatukannya ke image backend, tanpa port tambahan.
- **I-021 (implementasi):** Halaman login sesi Django+CSRF, pengambilan toko berdasarkan akses user, pilihan dapur/template, tanggal kirim, jadwal, tabel input Qty, cari/filter, simpan Draft, buka/edit lagi, dan Kirim Qty ≥1.
- **I-022 (penyederhanaan):** Tidak menambah microservice atau database. Ada management command idempotent `seed_order_schedules` untuk tiga jadwal standar bila belum ada.
- **I-023 (belum):** Auto-submit H-2 07.00 WIB, React frontend workspace lain, reverse proxy/HTTPS production, dan transaksi write ke Odoo tetap pekerjaan berikutnya.
- Panduan: [Workspace Admin Toko](./WORKSPACE-ADMIN-TOKO.md).

## Keputusan Qty integer untuk pemesanan toko — 2026-11-05
- **D-051 (✅):** Pengguna menetapkan **Qty input Admin Toko hanya integer** (0, 1, 2, ...), tidak menerima desimal.
- **I-024 (implementasi):** Frontend memakai input numerik digit saja, API Django memvalidasi integer nonnegatif. Draft tetap editable, dan Kirim hanya mengambil Qty ≥1.
- **I-025 (kompatibilitas):** Kolom Qty PostgreSQL masih Decimal(18,4) supaya tidak perlu migration berisiko; integritas bilangan bulat dijaga API. Draft historis yang punya pecahan diblokir saat Kirim sampai pengguna memperbaikinya.
- **Koreksi D-050:** Frasa Qty di bawah 1 dikeluarkan tetap berlaku untuk nol; **Qty pecahan kini tidak valid sejak tahap input**, bukan diizinkan lalu disaring saat Kirim.

## Implementasi auto-submit H-2 pukul 07.00 WIB (2026-11-05)
- **I-026 (✅ backend):** Perintah `auto_submit_store_orders` default preview, `--apply` baru bisa dipakai pada/pasca 07 WIB. Target tepat `delivery_date = tanggal_bisnis_WIB + 2 hari`; hanya Draft yang sudah ada.
- **I-027 (✅ integritas):** Qty integer ≥1 menjadi KIRIM, Draft kosong/Qty 0 menjadi NO_ORDER. Proses transaksi/row lock per order, audit `AUTO_KIRIM`/`AUTO_NO_ORDER`, `auto_submitted=true`; re-run aman dan tidak mengubah manual KIRIM.
- **I-028 (✅ deployment template):** Contoh `systemd` timer Debian pukul 07 WIB menggunakan `docker compose exec -T`. **Belum diaktifkan pada server pengguna**; perlu verifikasi preview sebelum operator meng-enable. Tidak menambah Celery/Redis.
- **I-029 (✅ kompatibilitas):** Draft historis dengan Qty pecahan/negatif tidak dikirim atau dibulatkan; ID dilaporkan dan unit mendapat status error untuk tindak lanjut operator. UI menandai KIRIM otomatis.
- **O-014 (❓ terbuka):** Kebijakan input/edit Draft **setelah** batas waktu 07 H-2 belum disepakati; versi ini tidak menolak late Draft dan tidak menjalankan ulang tiap menit. Harus diputuskan sebelum pemakaian tanpa pengawasan.
- **O-015 (❓ terbuka):** Prosedur backlog saat downtime di jam cutoff. Timer awal memilih `Persistent=false` agar tidak otomatis finalisasi data pengujian pada saat aktivasi malam hari.
- Panduan: [Auto-submit H-2](./AUTO-SUBMIT-H-2.md).

## Perbaikan pemeriksaan Store Order Line — 2026-11-05
- **I-030 (✅ UI Django Admin):** Tabel Store Order Line yang semula hanya menampilkan `StoreOrderLine object (id)` sekarang menampilkan toko, dapur, tanggal kirim, jadwal, SKU, nama produk, Qty dan status. Teks nama terkait juga dibuat informatif.
- **I-031 (✅ display integer):** Nilai basis data `78.0000` adalah bilangan bulat 78, jadi Django Admin menampilkan `78`; nilai historis pecahan ditandai untuk koreksi, tidak dibulatkan diam-diam.
- **I-032 (✅ pengamanan):** Halaman `Store orders` dan `Store order lines` di Django Admin menjadi **read-only**; tidak boleh add/edit/delete melalui admin agar keputusan Draft/Kirim dan validasi integer tidak bisa dilewati. Operator memakai Workspace Admin Toko untuk edit Draft.
- **Tidak ada migration:** Struktur PostgreSQL tetap sama dan aturan integer pada API tidak berubah.

## Implementasi Admin Produksi — Rekap Kebutuhan tahap awal (2026-11-06)
- **I-033 (✅ rekap read-only):** Endpoint `/api/v1/production/demand/` mengagregasi hanya **StoreOrder status KIRIM** untuk tanggal kirim, dapur, dan jadwal kirim terpilih. Menampilkan SKU, Qty total, dan asal per toko/order.
- **I-034 (✅ kejelasan status):** Toko yang `DRAFT`, `NO_ORDER`, atau belum membuat pesanan ditampilkan terpisah untuk meminimalkan salah interpretasi; ketiganya tidak masuk Qty rekap.
- **I-035 (✅ RBAC/UI):** Workspace React `/produksi/` khusus Group `PRODUCTION`, `ADMIN`, dan superuser; Group STORE tidak bisa membaca API produksi. Login memakai sesi Django yang sama di port 900.
- **I-036 (✅ integritas):** Rekap tidak menyaring SKU final berdasarkan flag template aktif saat ini; perubahan template tidak mengubah permintaan final. Data KIRIM historis yang Qty pecahan/nol memicu error 409 agar tidak dibulatkan diam-diam.
- **O-016 (❓ terbuka):** Penetapan `production_date` dan `production_schedule` dari tanggal/jadwal kirim, terutama produksi yang melewati tengah malam, harus dikonfirmasi sebelum membuat ProductionPlan. API rekap saat ini `production_date = null`.
- **I-037 (✅ batas):** Tahap ini hanya melihat kebutuhan SKU, **belum** memutuskan Qty produksi, pembulatan batch, kapasitas, stok bahan, atau MO Draft. Masalah auto-submit late Draft (O-014) tetap belum diselesaikan.
- Rujukan: [Workspace Admin Produksi](./WORKSPACE-ADMIN-PRODUKSI.md).

## Diagnostik rekap produksi — 2026-11-06
- **I-038 (✅ UX):** User melaporkan pesanan Toko Bandara/Kedaton sudah KIRIM, tetapi tidak tampak di rekap produksi. Pemeriksaan kode menunjukkan rekap memerlukan kecocokan **tanggal kirim + dapur + jadwal** persis, sedangkan frontend mengisi default H+2 dan jadwal pertama; data yang tidak cocok tampak NOT_ENTERED pada lingkup yang dipilih.
- **I-039 (✅ solusi diagnostik):** Tambah API read-only Group PRODUCTION/ADMIN `/api/v1/production/recent-orders/` (maksimal 30 KIRIM terbaru dari semua lingkup) dan panel **Temukan Pesanan yang Sudah Kirim**. Klik `Lihat rekap` menyelaraskan 3 filter tanpa mengubah data.
- **O-017 (perlu verifikasi data nyata):** Filter tepat untuk pesanan Toko Bandara/Kedaton baru dapat dipastikan dari database Debian operator. Tidak ada akses langsung ke PostgreSQL tenant pengguna dari GitHub.

## Koreksi alur antarmuka Admin Produksi — 2026-11-06
- **D-052 (✅ keputusan pengguna):** Halaman utama Admin Produksi adalah **daftar seluruh StoreOrder dengan status KIRIM atau PROSES_PRODUKSI**, bukan rekap yang memerlukan filter tanggal/dapur/jadwal lebih dulu.
- **D-053 (✅):** Setelah permintaan toko **benar-benar dikonsolidasi**, status `KIRIM → PROSES_PRODUKSI`. `DRAFT` dan `NO_ORDER` tidak tampil pada Admin Produksi.
- **I-040 (✅):** Tambah status `PROSES_PRODUKSI` ke StoreOrder dan migration 0003 untuk memperbesar CharField. Existing pesanan tetap KIRIM, tidak diubah saat upgrade.
- **I-041 (✅):** API `/api/v1/production/orders/` menampilkan KIRIM dan PROSES_PRODUKSI lintas tanggal/dapur/jadwal, filter dua status, pagination 50, akses hanya PRODUCTION/ADMIN. UI `/produksi/` langsung menampilkan antrean tersebut.
- **I-042 (✅):** Rekap per SKU menghitung KIRIM dan PROSES_PRODUKSI, tanpa menampilkan Draft/No Order; perubahan status tidak membuat Qty dihitung dua kali.
- **O-018 (batas fitur):** Tombol konsolidasi dan transisi status otomatis baru akan dibuat bersamaan dengan implementasi **ProductionPlan nyata**; belum boleh mengganti status hanya karena operator membuka rekap. Tanggal produksi/SOP lintas tengah malam tetap belum ditetapkan.
- **Koreksi I-033/I-034/I-038/I-039:** Desain default rekap berdasarkan filter dan panel pencarian KIRIM terbaru telah digantikan oleh antrean pesanan global. Endpoint lama boleh tetap untuk kompatibilitas tetapi UI utama tidak memakainya.
- Lihat [alur terbaru Admin Produksi](./WORKSPACE-ADMIN-PRODUKSI.md).

## Navigasi rekap tanpa kehilangan konteks — 2026-11-06
- **D-054 (✅ UX dari pengguna):** Tombol **Lihat rekap** di Admin Produksi membuka pop-up/modal di atas daftar antrean, bukan mengganti halaman atau menambahkan rincian panjang di bawahnya. Setelah ditutup pengguna tetap berada di daftar dan baris semula.
- **I-043 (✅):** React memakai native HTML `dialog`, fokus dialihkan ke tombol tutup, Escape/klik backdrop/tombol menutup modal, dan fokus dikembalikan ke tombol yang tadi membuka rekap. Filter/pagination/scroll antrean dipertahankan; rekap loading/error ada di dalam modal.
- **I-044 (✅ tes frontend):** Tambahkan unit interaction tests untuk buka rekap, tutup rekap, Escape dan pengembalian fokus via Vitest/jsdom di CI.

## Tampilan Qty integer dan UoM produk di Admin Produksi — 2026-11-06
- **D-055 (✅ pengguna):** Seluruh Qty integer pada daftar produksi dan rekap tidak boleh tampil seperti `1232.0000`; gunakan `1.232`, `120`, dst. Label generik `unit` tidak digunakan.
- **D-056 (✅):** Satuan per SKU **mengikuti UoM asli master produk** yang sudah tersedia dari Odoo pada `Product.uom`. Jika kosong gunakan **pcs**; bila satu pesanan memuat beberapa UoM berbeda, beri label **beragam UoM**, jangan salah sebut semua pcs.
- **I-045 (✅):** API produksi menormalkan nilai total integral dan menyertakan `uom` per produk serta `qty_uom` untuk total pesanan/rekap. Formatter React hanya menghapus pecahan nol, tanpa membulatkan nilai pecahan historis.
- **I-046 (✅):** Tes backend/frontend mencakup Qty `1232.0000`, fallback pcs, UoM asli, UoM campuran, dan desimal historis yang tidak boleh dibulatkan.
- Tidak mengubah skema PostgreSQL, BoM, sinkronisasi Odoo, atau satuan master.

## Keamanan pembacaan Qty operasional dan Multi UoM — 2026-11-06
- **D-057 (✅ penegasan pengguna):** Semua Qty pada layar operasional harus angka bulat dengan satuan yang jelas; `1.0000` tidak boleh dilihat sebagai angka Qty karena berisiko disalahartikan sebagai 10.000. `1 Pcs` harus tampak jelas sebagai `1 Pcs`.
- **D-058 (✅ konsep Multi UoM dari pengguna):** Representasi fisik `1,5 Kg` ditampilkan sebagai `1 Kg` dan `500 gram` pada baris terpisah bila format multi-satuan Odoo dipakai. **Ini aturan bisnis untuk fitur multi-UoM lanjutan; bukan kemampuan StoreOrderLine saat ini**, yang masih menyimpan satu `Product.uom` dan satu baris per `order + product`. Tidak boleh membuat konversi atau baris tambahan secara diam-diam.
- **I-047 (✅ pengamanan):** API antrean tidak lagi mengembalikan Qty pecahan historis sebagai angka siap-ditampilkan. Sebagai gantinya `qty_invalid=true`, `qty_total=null` dan UI menandai **Perlu koreksi Qty**. Rekap detail tetap menolak anomali dengan HTTP 409, tanpa pembulatan.
- **I-048 (✅ pengamanan multi UoM):** Untuk total berisi SKU dengan UoM berbeda, API tidak memberi satu nilai Qty gabungan (`qty_total=null`) dan menyediakan `qty_by_uom` terpisah, UI menampilkan masing-masing Qty + UoM. Contoh `1 Kg · 500 gram`, bukan `501 beragam UoM`. Ini **bukan konversi antar UoM**.
- **O-019 (❓ desain sistem berikutnya):** Untuk mendukung per produk multi-UoM/konversi dan baris sama SKU dengan unit berbeda diperlukan perluasan `StoreOrderLine`, tabel UoM/konversi yang sah, dan verifikasi dengan pemodelan Odoo sebelum implementasi.

## Keputusan baru: tanggal produksi manual (2026-11-06)
- **D-059 (✅ keputusan eksplisit pengguna):** Untuk konsolidasi pesanan, **`production_date` ditentukan manual oleh Admin Produksi**. Tidak otomatis mengikuti H-1/H-2 atau tanggal kirim. Contoh lingkup `JP / tanggal kirim 2026-11-07 / SUBUH` tidak memaksakan tanggal produksi tertentu.
- **I-049 (📄 kontrak, bukan implementasi):** Disusun [Kontrak Bisnis Konsolidasi Produksi V1](./KONTRAK-KONSOLIDASI-PRODUKSI-V1.md), meliputi lingkup pesanan KIRIM, Qty Requested → Planned, audit, anti-konsolidasi-ganda, transaksi atomik, dan transisi KIRIM → PROSES_PRODUKSI setelah penyimpanan.
- **O-020 (❓ harus diputuskan):** Apakah satu lingkup dapur × tanggal kirim × jadwal kirim harus menjadi **satu** rencana/tanggal produksi, atau boleh dipecah ke beberapa tanggal produksi; aturan pesanan KIRIM terlambat setelah rencana disimpan.
- **O-021 (❓):** Default/batas Qty Planned termasuk nilai nol, kebijakan tanggal produksi melewati tanggal kirim, perubahan tanggal produksi sesudah simpan, serta definisi jadwal produksi yang berbeda dari jadwal kirim.
- **I-050 (✅ audit desain):** Model `ProductionPlan` sudah punya `production_date` tetapi **belum punya relasi eksplisit ke StoreOrder**; constraint unik `(kitchen, production_date, delivery_date, schedule)` belum cukup mencegah satu pesanan masuk dua rencana bila tanggal produksinya berbeda. `ProductionPlanLine` juga mensyaratkan qty_mo/batch_qty/capacity_qty yang belum boleh diisi dummy untuk tahap konsolidasi awal.
- **Batas milestone:** dokumentasi/kontrak saja, **belum ada perubahan kode operasional**, migration, penyimpanan konsolidasi, atau write ke Odoo. Usulan tidak dianggap keputusan bisnis final.

## Pemisahan jadwal produksi dan kapasitas wajib — 2026-11-06
- **D-060 (✅ keputusan pengguna):** **`ProductionPlan` wajib mempunyai `production_date` dan `production_schedule`**, terpisah dari `delivery_date` dan `delivery_schedule`. Satu SKU bisa diproduksi pada tanggal yang sama dalam jadwal produksi berbeda untuk kelompok permintaan yang berbeda. Jadwal produksi tidak boleh disamakan diam-diam dengan jadwal kirim.
- **D-061 (✅):** Admin Produksi **berpegang pada tanggal dan jadwal pengiriman dari Admin Toko**. Permintaan `500 Pcs` untuk jadwal kirim `SUBUH` **tidak boleh dipecah/dialihkan** menjadi `250 SUBUH + 250 PAGI` oleh Admin Produksi; keputusan pembagian permintaan pengiriman adalah kewenangan Admin Toko.
- **D-062 (✅):** Workspace perencanaan Admin Produksi wajib menampilkan per SKU **Qty Pesan (`qty_requested`)**, **Qty Kapasitas Produksi** (berdasarkan SKU × jadwal produksi), dan **Qty Produksi (`qty_planned`)**, semua menggunakan UoM asli dan angka integer yang jelas. Qty Pesan tidak dapat diedit Admin Produksi.
- **I-051 (✅ audit model):** Model saat ini `ProductionPlan` baru punya satu `schedule`, **belum dua jadwal**. `ProductCapacity` sudah punya `product`, `schedule`, `max_qty` (unik SKU × jadwal), dan `ProductionPlanLine` sudah punya `qty_requested`, `qty_planned`, `capacity_qty`. UI form perencanaan/kapasitas **belum dibangun**, jangan salah mengklaim sudah ada.
- **O-022 (sebagian diselesaikan oleh D-063):** Konsolidasi **boleh disimpan jika Qty Produksi lebih rendah dari Qty Pesan akibat kapasitas tidak cukup**, dengan kekurangan tercatat. **Masih terbuka:** Qty Produksi melebihi kapasitas, approval, kapasitas yang terpakai rencana lain di slot sama, tindak lanjut kekurangan dan penentuan alokasi kekurangan per toko.
- **O-023 (❓):** Apakah satu komitmen pengiriman boleh **dilaksanakan** pada beberapa jadwal produksi dengan alokasi eksplisit tanpa mengubah Qty/jadwal kirim; keputusan tidak sama dengan izin mengubah jadwal kirim toko.
- **O-024 (❓):** Katalog jadwal produksi yang valid, dan apakah `Schedule` saat ini cukup atau memerlukan master terpisah. Migrasi skema jangan mengisi jadwal produksi historis menggunakan jadwal kirim secara asumtif.
- **Koreksi O-020/O-021 dan kontrak PR #17:** Larangan split harus merujuk ke **komitmen jadwal kirim**. Kemungkinan SKU pada tanggal produksi sama dalam beberapa jadwal produksi **telah ditegaskan boleh** untuk permintaan berbeda. Kapasitas bukan fitur yang boleh dihilangkan dari perencanaan V1.
- **Batas perubahan ini:** pembaruan **dokumen kontrak/PRD/Decision Log/README/panduan** saja, belum ada migrasi, API kalkulasi kapasitas, formulir Qty Produksi, atau penulisan ProductionPlan/Odoo. Rujukan: [kontrak terbaru](./KONTRAK-KONSOLIDASI-PRODUKSI-V1.md).

## Konsolidasi dengan kekurangan kapasitas boleh disimpan — 2026-11-06
- **D-063 (✅ keputusan eksplisit pengguna):** Admin Produksi **boleh menyimpan Qty Produksi 400 Pcs** ketika **Qty Pesan 500 Pcs** dan **kapasitas tersedia 400 Pcs**. **Kekurangan 100 Pcs wajib tercatat dan tetap terlihat** pada rencana produksi dan histori, bukan disembunyikan atau dianggap sudah dipenuhi.
- **D-064 (turunan langsung dari keputusan):** Qty/jadwal pengiriman toko tetap tidak berubah (500 Pcs untuk SUBUH). Kekurangan rencana = `max(0, qty_requested - qty_planned)`; selisih akibat batas kapasitas = `max(0, qty_requested - capacity_available)`. Dua angka itu dapat berbeda dan tidak boleh digabungkan.
- **I-052 (📄 kontrak, belum implementasi):** Perbarui kontrak Konsolidasi Produksi V1, PRD, panduan workspace, README. Simpan konsolidasi **belum tersedia**; tidak ada migration/API/DB/Odoo write pada PR dokumentasi ini.
- **O-025 (❓ terbuka):** Bagaimana kekurangan ditindaklanjuti dan dikaitkan ke setiap toko pada tahap Packing/distribusi; apakah membutuhkan approval atau status pemenuhan tersendiri; apakah Qty Produksi boleh nol, melampaui kapasitas, atau di atas Qty Pesan.
- **Batas penting:** status `PROSES_PRODUKSI` menandakan pesanan sudah masuk perencanaan, **bukan** seluruh Qty toko telah selesai diproduksi. Tahap MO masih harus validasi kapasitas ulang setelah pembulatan batch/BoM.

## Implementasi konsolidasi lokal pertama — 2026-11-06
- **I-053 (✅ implementasi API dan model):** Tambah `production_schedule` FK terpisah dari `delivery_schedule`, relasi `ProductionPlanSource.order` OneToOne + snapshot Qty/UoM, `ProductionPlanLine.qty_shortfall`, `capacity_used_before`; Qty MO/batch nullable agar tidak menciptakan data palsu. Migration 0004 menjaga jadwal kirim data lama, tidak menebak production_schedule historis.
- **I-054 (✅ backend):** Endpoint preview scope KIRIM, save atomik (row lock pesanan + kapasitas, snapshot, AuditLog, status PROSES_PRODUKSI hanya setelah berhasil), detail histori untuk menampilkan shortage tersimpan. Scope delivery V1 unik untuk rencana baru; tidak menduplikasi order.
- **I-055 (✅ frontend):** Tombol **Rencanakan** di antrean KIRIM, tabel per SKU Qty Pesan/Kapasitas/Terpakai/Tersisa/Produksi/Kekurangan, tanggal/jadwal produksi manual. **Lihat Rencana** pada status PROSES_PRODUKSI menampilkan detail read-only; **Lihat Rekap** modal tetap utuh.
- **D-065 (⚙️ batas aman sementara, BUKAN keputusan final pengguna):** Backend V1 membatasi `1 <= Qty Planned <= min(Qty Requested, Kapasitas Tersisa)` dan menolak kapasitas yang belum diatur. Kekurangan terhadap permintaan **tetap boleh disimpan** sesuai D-063. Aturan Qty Planned=0, Qty Planned>requested/kapasitas, dan mekanisme approval tetap terbuka untuk peninjauan bisnis.
- **O-026 (❓ tahap berikutnya):** Rekonsiliasi plan lama tanpa jadwal produksi, pesanan terlambat setelah rencana tersimpan, perubahan rencana, kapasitas tanggal/shift lintas dapur, alokasi kekurangan per toko, serta validasi ulang Qty MO setelah BoM batch dibulatkan.
- **Batas:** Tidak membuat MO, transfer, mengubah stok atau menulis ke Odoo. Status PROSES_PRODUKSI berarti pesanan telah masuk rencana, **bukan kebutuhan sepenuhnya terpenuhi**. Ketersediaan produksi nyata pada Debian harus diverifikasi setelah deployment/migrate, bukan disimpulkan dari CI.
