# Product Requirements Document (PRD) — RO Middleware
**Versi:** 0.1 (baseline diskusi)  
**Tanggal:** 2026-11-05  
**Status:** Draft untuk review; keputusan eksplisit ditandai *Disepakati*, usulan teknis ditandai *Usulan*.  
**Sumber:** Percakapan perancangan bisnis dalam ChatGPT, sampai pembahasan penyimpanan dokumen di GitHub.

## 1. Tujuan dan ruang lingkup
RO Middleware adalah aplikasi **mempercepat dan menyederhanakan input, konsolidasi, revisi perencanaan, serta pembentukan dokumen Draft di Odoo 19 SaaS**. Bukan ERP, inventory ledger, atau production scheduler kedua. Dashboard hanya pelengkap yang kelak dapat memakai data olahan middleware/Odoo.

### Empat workspace
1. **Admin Toko:** formulir massal SKU per dapur dan jadwal kirim; Draft/Kirim; histori.
2. **Admin Produksi:** konsolidasi pesanan, penyesuaian rencana SKU, pembulatan BoM, validasi kapasitas, kebutuhan bahan bersih plus buffer, finalisasi dan pembuatan Draft Odoo.
3. **Admin Packing:** penerimaan informasi realisasi produksi, prioritas perakitan PAKET, penyesuaian alokasi aktual ke toko dan dokumen distribusi.
4. **Administrator:** konfigurasi API, mapping/master operasional, pengguna dan hak akses, backup/restore, log integrasi, serta akses penuh ke semua workspace untuk QA; tindakan tetap diatribusi pada Administrator.

### Non-goals V1
Tidak menjadwalkan jam/shift kerja dapur, tidak mengatur SOP perpindahan dapur/WIP, tidak membuat MO berantai, tidak mengonfirmasi/menyelesaikan MO atau transfer, tidak menggantikan pembelian supplier atau stok Odoo. Batas status **Delivery Order** di Odoo masih perlu dikonfirmasi.

## 2. Warehouse dan stock location yang disepakati
| Warehouse | Location |
|---|---|
| Gudang Central | CDC/Stock |
| Dapur Packing | PCK/Packing |
| Dapur Asin | ASN/Stock |
| Dapur Cake Slice | CKS/Stock |
| Dapur Gorengan | GRG/Stock |
| Dapur Jajan Pasar | JP/Stock |
| Dapur Pastry | PST/Stock |
| Dapur Roti | ROTI/Stock |
| Dapur Sultan & Lemper | SUL/Stock |
| Dapur Tart | TART/Stock |
| Dapur Premik | PREMI/Stock |
| Dapur Legit | LEGIT/Stock |
| Toko Bandara | T_BAN/Stock |
| Toko Sudirman | T_SD/Stock |
| Toko Kedaton | T_KD/Stock |
| Toko Metro | T_MET/Stock |
| Toko Unila | T_UNI/Stock |
| Toko RSAM | T_RSA/Stock |
| Toko RS AIRAN | T_AR/Stock |

Jumlah: **19 warehouse**, yaitu 1 Central, 10 dapur produksi, 1 Packing, 7 toko. Kode source document menggunakan prefix sebelum `/` (mis. `ROTI`, `PCK`, `CDC`).

## 3. Kepemilikan data
| Domain | System of record |
|---|---|
| SKU, kategori, BoM, komponen, warehouse, location, stok aktual | **Odoo → Middleware** |
| Mapping SKU → dapur aktif | **Middleware**, mapping dapur kerja yang dipakai untuk perencanaan dikelola middleware; sumber *initial assignment* belum diputuskan. Pada saat membuat MO, lokasi/dapur produksi ditentukan oleh **Manufacturing Operation Type Odoo** (picking_type_id), bukan Product Category. Sinkronisasi master tidak boleh menimpa keputusan operator |
| Kapasitas per SKU per jadwal; jadwal produksi/kirim | Middleware |
| Parameter minimum stok Premix/WIP per warehouse | Middleware |
| Permintaan toko, revisi, konsolidasi, alokasi, identitas middleware | Middleware |
| MO & transfer aktual/status stok resmi | Odoo |

SKU umumnya memiliki satu dapur aktif untuk kebutuhan perencanaan, tetapi **MO yang dibuat harus menggunakan Operation Type manufaktur milik dapur tujuan**. Operation Type pada MO adalah penentu operasional di Odoo; kategori produk hanya grouping. SKU dapat dipindah dapur sesuai SOP; middleware tidak mengatur bentrok proses fisik. Simpan dapur snapshot saat rencana/MO dibuat. Odoo sudah dikonfigurasi agar BoM tidak memicu BoM/MO lain.

## 4. Alur permintaan toko
- Toko memilih **tanggal pesan, tanggal kirim, jadwal kirim**. **Tanggal produksi dipilih manual oleh Admin Produksi saat konsolidasi**; aturan pemetaan **jadwal produksi** dari jadwal kirim masih perlu diputuskan.
- Input dilakukan **per toko × dapur × tanggal/jadwal kirim**; satu dapur bisa punya 50–700 SKU. Katalog sudah disiapkan, pengguna cukup isi Qty.
- Status **Draft**: Qty dapat diedit. Status **Kirim**: Qty terkunci untuk Admin Toko; hanya status Kirim masuk konsolidasi.
- Submit manual atau auto-submit pada **07.00 WIB, H-2** terhadap tanggal kirim. H-2 adalah 2 hari kalender.
- Ketika submit, buang baris Qty = 0, simpan baris **Qty ≥ 1**. Bila semuanya nol, catat **No Order** (bukan error); toko bisa libur pada hari tertentu.
- Status submit per dapur terpisah. Konsolidasi hanya atas permintaan yang sudah Kirim.

## 5. Jadwal kirim versus jadwal produksi serta tiga tanggal
Tanggal **pesan**, **produksi**, dan **kirim** tetap terpisah. Terdapat tiga jadwal standar dan dapat ditambah jika diperlukan:
1. Kirim **subuh** → produksi sekitar 20.00 malam sebelumnya sampai subuh.
2. Kirim **pagi sekitar 08.00** → produksi subuh sampai 08.00.
3. Kirim **siang** → produksi 08.00–10.00.
SOP mengatur waktu dan eksekusi; middleware **bukan scheduler aktivitas fisik dapur**. **Tanggal produksi diisi manual oleh Admin Produksi dan jadwal produksi harus tercatat terpisah dari jadwal kirim.** SKU yang sama dapat diproduksi pada satu tanggal di jadwal produksi berbeda untuk kebutuhan pengiriman yang memang berbeda. Admin Produksi **tidak boleh memecah atau mengubah permintaan 500 Pcs jadwal kirim SUBUH menjadi 250 SUBUH + 250 PAGI**. Batas tanggal, sumber daftar jadwal produksi dan kemungkinan alokasi produksi lintas jadwal untuk permintaan yang sama memerlukan aturan tersendiri.

## 6. Konsolidasi MO produk jadi
- Calon konsolidasi berasal dari StoreOrder **KIRIM** dengan lingkup **dapur × tanggal kirim × jadwal kirim** yang tidak boleh diubah oleh Admin Produksi. Rencana memiliki dimensi **tanggal produksi (manual) × jadwal produksi (terpisah)**. SKU yang sama bisa muncul pada tanggal produksi sama dengan jadwal produksi berbeda untuk kelompok pengiriman yang berbeda; Qty sumber tidak boleh dihitung dua kali atau dipecah ke jadwal kirim lain. Kebijakan pembagian *pelaksanaan produksi* lintas shift untuk satu kelompok pengiriman masih perlu keputusan.
- **Tabel perencanaan wajib menampilkan berdampingan**: **Qty Pesan (`qty_requested`)**, **Qty Kapasitas Produksi (`ProductCapacity.max_qty` untuk SKU × jadwal produksi)**, dan **Qty Produksi (`qty_planned`, keputusan Admin Produksi)**. Seluruh nilai menggunakan UoM yang benar, tanpa angka pecahan yang berpotensi salah dibaca. Qty Pesan asli tidak dapat diedit. Bila kapasitas belum dikonfigurasi, tampilkan **Kapasitas belum diatur**, bukan 0 atau tak terbatas. Perbedaan permintaan vs kapasitas harus terlihat; tidak boleh mengalihkan Qty ke jadwal kirim lain secara otomatis.
- Simpan terpisah: `qty_requested` (asli agregat toko), `qty_planned` (dapat direvisi Admin Produksi), `capacity_qty` (snapshot kapasitas untuk jadwal produksi), `qty_mo` (kelipatan BoM; tahap berikutnya).
- Kuantitas target: `qty_mo = ceil(qty_planned / bom_output_qty) * bom_output_qty` untuk qty_planned > 0.
- **Kekurangan boleh tersimpan:** bila Qty Pesan = **500 Pcs**, kapasitas tersedia = **400 Pcs**, Admin Produksi boleh menyimpan **Qty Produksi = 400 Pcs** dengan **Qty Kekurangan = 100 Pcs** yang tetap tercatat/terlihat. Qty Pesan dan jadwal kirim toko tidak berubah; konsolidasi tersimpan **bukan** bukti pemenuhan seluruh Qty Pesan. Rumus `qty_shortfall = max(0, qty_requested - qty_planned)`; pisahkan dari `capacity_gap = max(0, qty_requested - capacity_available)`.
- **qty_mo ≤ kapasitas SKU per jadwal produksi** tetap menjadi validasi tahap MO setelah pembulatan BoM; penyimpanan konsolidasi dengan kekurangan tidak otomatis mengesahkan Qty MO. Sistem wajib menampilkan selisih, **tidak boleh memotong/memindahkan jadwal kirim**. Aturan ketika Qty Produksi melebihi kapasitas, approval kekurangan, kapasitas yang sudah dipakai rencana lain, serta tindak lanjut per toko masih terbuka.
- Revisi hanya hingga MO dibuat; perubahan Qty rencana mengulang hitung BoM/bahan. Audit otomatis nilai lama/baru, pelaku, timestamp tanpa formulir alasan wajib.
- Hasil aktual dapat kurang/lebih dari output BoM (rusak, variasi ukuran); tidak boleh memaksa sama dengan target.

## 7. Bahan baku dan replenishment
- Untuk setiap dapur dan jadwal produksi: jumlahkan komponen langsung BoM dari **qty_mo**, kemudian kurangi stok tersedia **di dapur itu**. Tidak memakai agregat stok seluruh perusahaan.
- `minimum_request = max(0, gross_bom_requirement - available_kitchen_stock)`.
- Admin Produksi bisa menambah `buffer_extra ≥ 0`, sehingga `requested_transfer = minimum_request + buffer_extra`, termasuk ketika minimum nol.
- Hitung urutan jadwal dengan benar agar stok tidak dipakai mengurangi dua jadwal sekaligus; stok di Odoo berubah sehingga perlu revalidasi sebelum submit ke Odoo.
- Supplier memasok bahan ke **CDC/Stock**; Central menyuplai dapur. Antar-dapur dapat transfer WIP sesuai SOP; **middleware tidak menjadwalkan perpindahan WIP**.
- Premix diproduksi di Central (campur bahan menjadi SKU baru), WIP di dapur (proses produksi). Minimum stok per SKU × warehouse disimpan di middleware. MO Premix/WIP berdasar replenishment terpisah, **bukan dipicu MO produk jadi**. Implementasi trigger/approval replenishment belum final.

## 8. PAKET dan Packing
- SKU kategori **PAKET** sudah memiliki BoM di Odoo, dipesan langsung oleh toko, dikonsolidasi oleh Admin Produksi, dan menghasilkan **MO Draft perakitan di PCK/Packing**.
- BoM Paket menunjukkan komponen; tidak boleh mengakibatkan pembuatan MO berantai otomatis.
- Di Packing, kebutuhan komponen **PAKET diprioritaskan atas distribusi produk satuan**. Kekurangan produk satuan akibat prioritas PAKET dapat diterima.
- Produk hasil dapur dikirim ke Packing; aktual transfer bisa berbeda dari MO. **Packing tidak menyimpan sisa produk jadi semalam**: seluruh hasil produksi yang diterima didistribusikan hari yang sama.
- Admin Packing mengubah **qty_alokasi_aktual per toko**, bisa lebih/kurang dari pesanan asli, tanpa mengubah pesanan. Cara mendeteksi/menangani stok yang tidak cukup bagi Paket ditetapkan di proses packing; penambahan kebutuhan komponen Paket ke rencana dapur **belum diputuskan**.

## 9. Integrasi Odoo V1
- Setelah Admin Produksi menyelesaikan **konsolidasi bahan baku**, baru middleware membuat **MO dan Stock Transfer dalam status Draft** di Odoo.
- Tidak mengonfirmasi, mengeksekusi WO, atau memvalidasi transfer di V1; aktivitas fisik mengikuti SOP di Odoo.
- Odoo merupakan sumber status transaksi dan stok resmi. Simpan `odoo_model`, `odoo_record_id`, status sinkronisasi, request id, error, retry.
- Gunakan integrasi JSON-2 sesuai dukungan paket/izin Odoo Online. Credential harus aman. Operasi multi-dokumen tidak atomik lintas panggilan: cegah duplikasi dan tangani partial success.
- Saat membuat MO Draft, gunakan `mrp.production.picking_type_id` yang sesuai dapur produksi/packing terpilih. ID dan hubungan Operation Type ↔ warehouse harus dibaca dan diverifikasi dari Odoo; **jangan** ditentukan lewat Product Category. Detail konfigurasi mapping menunggu hasil pemeriksaan tenant.
- Field `Source Document` dihasilkan middleware. **Format** `KODE-YYMMDD-COUNTER`; kode tanpa `/Stock` atau `/Packing`, waktu pembuatan dokumen **WIB**, counter **per warehouse per hari** mulai `10001`. Identitas referensi middleware tidak menggantikan nomor native Odoo.

## 10. UX, arsitektur dan kebutuhan nonfungsional
- **Frontend:** React + TypeScript + Vite; visual mengacu SAP Fiori/Horizon (referensi desain, bukan copy aset); tabel compact, input keyboard, pencarian SKU, edit massal, performa daftar 50–700 SKU.
- **Backend:** Django + Django REST Framework. **DB:** PostgreSQL melalui Docker. **Jobs:** Redis + Celery + Celery Beat (termasuk auto-submit WIB 07.00). Docker Compose, modular monolith.
- Audit trail perubahan planning, konfigurasi, alokasi, submit, dan integrasi; RBAC empat workspace, Administrator superuser QA dengan identitasnya sendiri.
- Backup/restore khusus middleware, bukan backup database Odoo; restore tidak boleh menyebabkan push ulang transaksi Odoo.
- Idempotensi integrasi, lock/transaksi lokal dan constraint unik; observability sync/error; pengecekan stok saat konsolidasi dan sebelum push.

## 11. Acceptance criteria V1 (ringkas)
1. Dua permintaan toko berbeda untuk SKU/dapur/jadwal sama menghasilkan satu baris konsolidasi dengan trace ke masing-masing toko.
2. Draft per dapur dapat diedit, Kirim terkunci; submit otomatis H-2 07.00 WIB; semua nol → No Order.
3. Untuk BoM output 100, plan 210 menghasilkan MO qty 300; rencana yang menghasilkan MO melebihi kapasitas ditolak untuk diproses.
4. Gross bahan dihitung dari MO yang sudah dibulatkan, stok dapur dikurangi sekali, buffer menambah transfer.
5. Qty permintaan asli tidak berubah saat rencana atau alokasi distribusi disunting.
6. API gagal di tengah batch: status parsial tercatat, retry tidak membuat dokumen ganda.
7. Dokumen MO dan transfer dibuat Draft; referensi source document unik per kode/tanggal/counter.
8. Paket dipesan seperti SKU lain, MO Draft menuju Packing, prioritas paket ditampilkan saat alokasi.
9. Administrator dapat memakai keempat workspace untuk QA; tindakan tercatat dengan akun Administrator.

## 12. Hal terbuka — jangan diasumsikan sudah disepakati
- Aturan saat permintaan melebihi kapasitas efektif setelah pembulatan.
- Kebijakan validasi **tanggal produksi pilihan manual** (batas terhadap tanggal kirim, lintas tengah malam), sumber jadwal produksi yang valid, dan apakah satu lingkup pengiriman boleh dilaksanakan di lebih dari satu tanggal/jadwal produksi **tanpa mengubah jadwal kirim**.
- Apakah kebutuhan komponen PAKET ikut agregat demand produksi dapur atau informasi saja.
- Ketentuan DO toko: status Draft atau langsung Confirm, beserta transfer dapur→Packing.
- Urutan referensi source document untuk transfer dua warehouse: kode warehouse asal atau tujuan (usulan asal).
- Detail replenishment Premix/WIP: titik trigger, approval, target qty di atas minimum.
- Batas akses pengguna per toko, penanganan pengembalian/koreksi, sinkronisasi stok, snapshot BoM, kuantitas satuan/UoM dan precision.
- Mapping awal SKU→dapur: metode input/operator atau referensi MO historis belum dipilih; yang pasti routing tiap MO ditentukan Operation Type di Odoo.
- Infrastruktur hosting dan kebijakan RPO/RTO backup.

> Dokumen ini baseline requirements, bukan bukti validasi langsung API/model Odoo pada tenant produksi.

## Addendum 2026-11-05 — Template SKU manual per dapur (keputusan terbaru)
- Admin/Administrator mengelola **daftar SKU yang ditawarkan pada formulir pemesanan** per dapur, menggunakan upload Excel `.xlsx` dan edit manual di middleware. Tidak ada pemilihan dapur otomatis dari Product Category.
- Template per dapur berlaku sebagai katalog bersama untuk toko-toko; saat Admin Toko memilih dapur, sistem langsung menampilkan daftar `SKU/ID | Nama Produk | Qty` dengan Qty default 0. Pengguna cukup mengisi Qty massal, **tidak menginput SKU satu per satu**.
- Template memiliki **flag Aktif/Nonaktif per SKU** dan urutan tampil. SKU nonaktif disembunyikan dari formulir pesanan baru, tetapi tidak menghapus histori order maupun master Odoo.
- `ProductionAssignment` digunakan untuk satu pemetaan SKU→dapur serta template list, sehingga **tidak perlu tabel header template lain** pada V1. Semua perubahan assignment dan aktif template milik middleware.
- Upload aman: preview sebelum impor; validasi SKU mengacu ke master Odoo; SKU tidak ditemukan, duplikat, atau sudah ditempatkan di dapur lain dilaporkan dan tidak diimport secara parsial; SKU yang absen dari Excel baru tidak dihapus otomatis.
- **Operation Type Odoo tetap penentu lokasi produksi pada MO.** Template manual hanya menentukan SKU yang muncul untuk pemesanan/perencanaan; ketika membuat MO, middleware harus mengirim Operation Type sesuai dapur.
- Spesifikasi dan petunjuk: [Template Pemesanan per Dapur](./TEMPLATE-PEMESANAN.md).

## Addendum — Detail Simpan Draft / Kirim pada formulir Admin Toko (2026-11-05)
- **Simpan Draft bukan submit:** dapat dibuka kembali berkali-kali, Qty yang sudah dimasukkan dipertahankan dan masih dapat diubah/di-nol-kan sampai pengguna memilih Kirim.
- **Kirim:** hanya baris Qty ≥ 1 yang diproses; baris Qty 0 (atau yang lebih kecil dari 1) dikeluarkan. Status menjadi KIRIM dan Qty terkunci bagi Admin Toko.
- **No Order:** bila seluruh Qty tidak memenuhi minimum, status `NO_ORDER` tanpa MO, kondisi normal untuk toko yang libur.
- Per toko × dapur × delivery date × delivery schedule tetap berstatus independen; hanya order KIRIM masuk konsolidasi.
- Kuantitas Draft yang sudah tersimpan tidak hilang diam-diam jika template dapur kemudian diubah. Formulir edit dapat memperlihatkan item lama tersebut dengan status tidak aktif di template untuk diperiksa.
- Implementasi awal API: [Admin Toko — Draft dan Kirim](./ADMIN-TOKO-DRAFT-KIRIM.md). Auto-submit H-2 07.00 WIB tetap direncanakan, belum otomatis berjalan.

## Implementasi UI Admin Toko — 2026-11-05
- React + TypeScript + Vite mengimplementasikan form massal Qty berdesain enterprise SAP Fiori Horizon-inspired, memakai satu host Django `/toko/` port **900**.
- Login berbasis Django Session+CSRF; user toko hanya boleh mengakses warehouse toko yang ditugaskan; Administrator dapat melakukan QA dan tindakan tetap tercatat atas dirinya.
- Pilih Toko, Dapur (template manual), Tanggal Kirim (nilai awal H+2 WIB), Jadwal Kirim; tampilkan SKU/ID + Nama Produk + Qty.
- Sediakan pencarian, filter Qty ≥1, input keyboard Enter/Tab, Simpan Draft/edit ulang, Kirim terkunci. Dapurnya dapat menampilkan ratusan SKU (praktis sampai 700) tanpa form pilih produk satu per satu.
- V1 ini mengakses API middleware saja, tidak membuat MO atau transfer Odoo; auto-submit H-2 pukul 07.00 WIB tetap perlu milestone lanjutan.

## Addendum — Qty Admin Toko wajib integer (2026-11-05)
- **Qty pada formulir pemesanan toko hanya bilangan bulat nonnegatif**: `0, 1, 2, 3, ...`. Tidak boleh desimal (termasuk `1.5`).
- **Simpan Draft** tetap bisa diedit; Qty 0 diperbolehkan. **Kirim** hanya menyertakan baris Qty ≥1, seluruh bilangan bulat. Jika semuanya 0 → `NO_ORDER`.
- Validasi dilakukan di **frontend dan backend**; API menolak nilai desimal dari klien lain. Draft historis yang sudah terlanjur berisi Qty desimal harus diperbaiki oleh operator sebelum Kirim, **tanpa pembulatan otomatis**.
- Batas ini berlaku pada **input Qty pesanan toko**, bukan jumlah bahan baku/BoM atau UoM lain di Odoo. Tidak perlu migration PostgreSQL untuk perubahan input ini.

## Milestone backend Auto-submit H-2 07:00 WIB (2026-11-05)
- Command backend membaca tanggal Asia/Jakarta dan pada/pasca jam 07:00 H-2 memfinalisasi Draft **yang sudah tersimpan** untuk delivery date H+2, semua toko/dapur/slot. Hanya Qty integer ≥1 dipertahankan; seluruh nol/empty menjadi NO_ORDER. Lock dan audit otomatis.
- Default preview read-only; `--apply` eksplisit dan command tidak boleh dijalankan sebelum cutoff WIB. Re-run tidak menggandakan order karena status KIRIM/NO_ORDER dikecualikan dan row lock transaksi.
- Template timer systemd tersedia; **baru bekerja otomatis setelah administrator meng-enable di Debian**, bukan langsung saat deploy code.
- Manual Kirim dan Auto Kirim memakai status yang sama untuk konsolidasi, dibedakan `auto_submitted` dan audit log.
- **Belum final:** apakah API harus menolak edit/new Draft setelah cutoff 07 H-2, dan apakah downtime harus otomatis catch-up. Jangan anggap fungsi cutoff benar-benar enforcement sampai kebijakan ini disepakati.

## Milestone Admin Produksi — Rekap read-only (2026-11-06)
- `KIRIM` per toko adalah satu-satunya sumber rekap kebutuhan. API dan React menampilkan **tanggal kirim × dapur × jadwal kirim → total Qty per SKU**, dengan rincian order/toko.
- Status toko DRAFT, NO_ORDER, dan belum membuat pesanan dipantau terpisah, tanpa memasukkan Qty mereka ke total.
- Rekap final tetap menyertakan SKU yang saat ini dipindahkan/nonaktif pada template middleware, untuk menjaga histori pesanan final.
- Akses khusus Group PRODUCTION/ADMIN/superuser, tanpa hak mengedit pesanan toko.
- Tahap ini **read-only**: tidak membuat ProductionPlan, tidak memanggil API tulis Odoo. **Tanggal produksi dan jadwal produksi belum otomatis diturunkan** dari tanggal/jadwal pengiriman sampai SOP-nya ditetapkan.
- Detail pengujian: [Workspace Admin Produksi](./WORKSPACE-ADMIN-PRODUKSI.md).

## Koreksi final Workspace Admin Produksi (2026-11-06)
- **Inbox pertama kali membuka SEMUA pesanan yang berstatus KIRIM atau PROSES_PRODUKSI**, tanpa filter tanggal/dapur/jadwal default, dan dapat difilter per status. Pagination mencegah pesanan lama tidak terlihat.
- Tidak menampilkan Draft/No Order di Workspace Admin Produksi. Draft tetap milik Admin Toko.
- **KIRIM** = permintaan diserahkan toko, menunggu konsolidasi. **PROSES_PRODUKSI** = permintaan sudah masuk konsolidasi rencana produksi. Semua Qty/asal toko tetap terlacak dan read-only bagi toko.
- Ketika membuat ProductionPlan sungguhan, transisi `KIRIM → PROSES_PRODUKSI` dilakukan **dalam transaksi konsolidasi berhasil**, bukan sebagai perubahan status tanpa artefak perencanaan.
- Rincian per tanggal kirim, dapur, dan jadwal dapat dibuka dari baris antrean (bukan syarat awal agar pesanan terlihat). Rekap dapat menghitung kedua status sekali per order.
- Status `PROSES_PRODUKSI` disiapkan pada DB dan API, tetapi **belum dapat ditransisikan melalui frontend** hingga fitur konsolidasi ProductionPlan dibangun. Tidak ada write ke Odoo.
- Referensi implementasi [Workspace Admin Produksi](./WORKSPACE-ADMIN-PRODUKSI.md).

## Keputusan tanggal produksi manual dan kontrak konsolidasi (2026-11-06)
- **DISEPAKATI:** Tanggal produksi **ditentukan manual oleh Admin Produksi saat konsolidasi**, tidak otomatis H-1, H-2 atau sama dengan tanggal kirim. Field wajib dipilih operator sebelum simpan.
- Status tetap `KIRIM → PROSES_PRODUKSI` **hanya setelah rencana konsolidasi lokal tersimpan atomik** beserta rincian SKU dan relasi pesanan sumber. Lihat rekap/pratinjau tidak mengubah status.
- **DISEPAKATI:** ProductionPlan harus membedakan **tanggal + jadwal produksi** dari **tanggal + jadwal kirim**. SKU yang sama boleh diproduksi pada tanggal sama dalam jadwal produksi berbeda untuk kebutuhan kirim yang berbeda. Kebutuhan toko **500 Pcs SUBUH** tidak boleh dibagi menjadi **250 SUBUH + 250 PAGI** oleh Admin Produksi.
- **DISEPAKATI:** Admin Produksi harus melihat **Qty Pesan, Qty Kapasitas Produksi, Qty Produksi** berdampingan per SKU dan UoM sebelum menentukan Qty Produksi.
- **USULAN**, belum disahkan: satu kelompok pengiriman × SKU → satu alokasi rencana produksi, Qty Planned integer per SKU, relasi sumber dan kunci anti-duplikasi. Keputusan apakah satu komitmen pengiriman boleh dilaksanakan dalam beberapa jadwal produksi masih terbuka, tetapi **tidak boleh mengubah jadwal pengirimannya**.
- **DISEPAKATI:** Qty Produksi dapat disimpan lebih kecil daripada Qty Pesan jika kapasitas tidak mencukupi, dengan **kekurangan tercatat dan terlihat**; contoh 500/400/400 → kurang 100 Pcs. Tidak ada perubahan Qty/jadwal kirim dan tidak ada pemenuhan otomatis.
- **TERBUKA:** kebijakan alokasi pelaksanaan produksi lintas tanggal/jadwal untuk *komitmen pengiriman yang sama*, revisi, order terlambat, approval dan tindak lanjut kekurangan (termasuk alokasi per toko), Qty Produksi > kapasitas, aturan Qty Planned=0/default, pengaturan jadwal produksi yang valid dan batas tanggal.
- **Sudah diimplementasikan pada tahap konsolidasi lokal:** penyimpanan ProductionPlan, relasi snapshot ke StoreOrder, perpindahan status setelah simpan atomik. **Belum diimplementasikan:** MO/transfer Odoo, BoM batch/qty_mo, revisi dan distribusi kekurangan.
- **Migrasi skema selesai pada milestone konsolidasi:** migration `0004` memisahkan `ProductionPlan.delivery_schedule` dan `production_schedule` (nullable untuk plan historis). Kapasitas `ProductCapacity.max_qty` berdasarkan `product + production_schedule` sekarang ditampilkan di layar perencanaan beserta Qty kapasitas yang terpakai/tersisa dan Qty Kekurangan.
- Kontrak rincinya ada pada [Kontrak Bisnis Konsolidasi Produksi V1](./KONTRAK-KONSOLIDASI-PRODUKSI-V1.md). Dokumentasi ini menjadi referensi sebelum implementasi; usulan bukan persetujuan otomatis.

## Addendum implementasi Konsolidasi Produksi V1 (2026-11-06)
- Frontend `/produksi/` kini memiliki tindakan **Rencanakan** pada order KIRIM; form berisi **Tanggal Produksi manual** dan **Jadwal Produksi terpisah**, ditambah per SKU **Qty Pesan / Kapasitas Master / Terpakai / Tersisa / Qty Produksi / Kekurangan**. Modal Lihat Rekap tetap read-only.
- Backend preview hanya mengambil order **KIRIM** pada dapur × tanggal kirim × jadwal kirim, memverifikasi integer Qty, dan menghitung kapasitas `ProductCapacity` menurut SKU × jadwal produksi, dikurangi Qty rencana lain pada tanggal/jadwal produksi yang sama.
- Simpan konsolidasi V1 menghasilkan **ProductionPlan DRAFT lokal**, ProductionPlanLine dengan Qty Requested/Planned/Capacity/Shortfall, ProductionPlanSource (snapshot toko), AuditLog, dan baru kemudian `KIRIM → PROSES_PRODUKSI` secara atomik. Shortfall 500/400/400 → 100 Pcs tersimpan, tanpa mengubah pesanan toko.
- **Batas konservatif belum diputuskan permanen:** Planned harus integer **1 sampai min(Requested, Kapasitas Tersisa)**. Kapasitas belum dikonfigurasi ⇒ blokir simpan. Satu lingkup pengiriman hanya satu rencana (belum mendukung split satu scope); jadwal produksi diambil dari master Schedule yang aktif. Belum ada MO, perhitungan batch, transfer/Odoo write atau revisi Qty plan setelah disimpan.
- **Migration 0004** memisahkan `ProductionPlan.delivery_schedule` dan `production_schedule`, mempertahankan jadwal kirim historis, membiarkan production_schedule pada plan lama NULL, dan menambahkan relasi snapshot order + kekurangan. ProdPlanLine.qty_mo/batch_qty NULL hingga perhitungan MO dilakukan, bukan angka rekayasa.
- Implementasi ini menutup fitur dasar konsolidasi lokal; keputusan bisnis lain tetap terbuka, termasuk Qty Planned=0, overcapacity, rencana split, pesanan terlambat, penanganan kekurangan per toko dan persetujuan revisi.
- Panduan terbaru: [Workspace Admin Produksi](./WORKSPACE-ADMIN-PRODUKSI.md), [Kontrak Konsolidasi V1](./KONTRAK-KONSOLIDASI-PRODUKSI-V1.md).

## UX modal konsolidasi tanpa kehilangan konteks (2026-11-06)
- **DISEPAKATI:** **Rencanakan** dan **Lihat Rencana** memiliki perilaku navigasi yang sama seperti **Lihat Rekap**: native modal/pop-up di atas daftar Admin Produksi. Bukan layar halaman pengganti, bukan konten yang turun di dalam halaman, dan bukan window browser baru.
- Daftar belakang tidak di-unmount. Paginasi, filter, posisi scroll, dan baris sumber tetap utuh. Pop-up mempunyai area scroll vertikal mandiri, tabel dapat scroll horizontal, dan footer simpan/tutup tetap terlihat.
- ×, tombol Tutup/Batal, Esc, dan backdrop menutup modal tanpa simpan. Fokus dikembalikan ke tombol pemicu pada baris asli. Modal tidak ditutup selama request Simpan aktif.
- Setelah simpan berhasil, rencana tersimpan ditampilkan di modal yang sama; **refresh inbox dilakukan saat modal ditutup**, dan fokus diarahkan ke **Lihat Rencana** pengganti pada baris itu (atau tab aktif bila baris keluar dari filter KIRIM).
- Perubahan ini **frontend-only**, tanpa perubahan business rule Qty, kapasitas, status, API, skema DB maupun MO/Odoo. Pengujian React wajib memverifikasi keberadaan antrean di belakang modal dan pengembalian fokus sesudah tombol/Esc maupun setelah simpan.


## Produk ke dapur dan kapasitas produksi dalam satu proses administrasi (2026-11-06)
- **Disepakati:** Admin mengisi/mengubah SKU di template dapur sekaligus mengisi **kapasitas produksi SKU per jadwal** pada form yang sama. Tidak perlu membuka menu kapasitas terpisah untuk setiap produk.
- Download/Upload Excel template dapur menyertakan kolom `KAPASITAS_<KODE_JADWAL>` dari jadwal produksi aktif; satu preview, validasi (integer, nonnegatif, tidak ada rumus/kolom jadwal tidak aktif), impor atomik + audit.
- Kapasitas `0` berarti tidak ada kapasitas; sel kosong mempertahankan kapasitas lama atau belum diatur untuk SKU baru. Konsolidasi tidak boleh memperlakukan kosong sebagai tidak terbatas. UoM kapasitas mengikuti master produk Odoo; Qty harus bulat.
- Model `ProductionAssignment` tetap satu dapur per SKU; kapasitas tetap `ProductCapacity(product,schedule,max_qty)` agar multi-jadwal tetap normalisasi, meskipun form dan impor digabung. Perpindahan SKU dengan kapasitas lama ke dapur baru memerlukan konfirmasi.


## Pembaruan 8 November 2026 — Informasi hasil 1 resep BoM

- Kolom **Hasil 1 Resep BoM** menginformasikan output resep dari master Odoo, misalnya **100 Pcs**. Informasi ini tidak menentukan jumlah resep, mengisi Qty, atau membulatkan produksi otomatis.
- **Qty Produksi** (`qty_planned`) tetap diisi manual oleh Admin Produksi. Untuk kebutuhan 150 dan kapasitas 300, operator boleh memilih 200 atau 300; sistem menyimpan persis angka yang dimasukkan, selama integer positif dan tidak melebihi kapasitas tersisa. Batas sementara Qty Planned ≤ Qty Requested digantikan oleh keputusan ini.
- Kekurangan = `max(0, requested - planned)`. Kelebihan = `max(0, planned - requested)`, hanya ditampilkan tanpa alokasi otomatis. Pesanan dan jadwal kirim toko tetap utuh.
- Informasi BoM yang belum tersedia diberi label **Belum tersedia**, tanpa menebak resep atau memblokir penyimpanan manual karena informasi tersebut. `qty_mo` dan `batch_qty` tetap NULL pada rencana baru; tidak ada perhitungan batch atau MO Odoo pada tahap ini.
- Kelebihan belum otomatis dijadikan WIP atau dibagi prorata. Pengaturan alokasi aktual tetap di tahap Packing; kebijakan WIP/prorata belum diputuskan.
