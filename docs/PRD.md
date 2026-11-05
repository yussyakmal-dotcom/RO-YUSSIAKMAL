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
- Toko memilih **tanggal pesan, tanggal kirim, jadwal kirim**. Sistem memetakan jadwal kirim ke jadwal produksi.
- Input dilakukan **per toko × dapur × tanggal/jadwal kirim**; satu dapur bisa punya 50–700 SKU. Katalog sudah disiapkan, pengguna cukup isi Qty.
- Status **Draft**: Qty dapat diedit. Status **Kirim**: Qty terkunci untuk Admin Toko; hanya status Kirim masuk konsolidasi.
- Submit manual atau auto-submit pada **07.00 WIB, H-2** terhadap tanggal kirim. H-2 adalah 2 hari kalender.
- Ketika submit, buang baris Qty = 0, simpan baris **Qty ≥ 1**. Bila semuanya nol, catat **No Order** (bukan error); toko bisa libur pada hari tertentu.
- Status submit per dapur terpisah. Konsolidasi hanya atas permintaan yang sudah Kirim.

## 5. Jadwal dan tiga tanggal
Tanggal **pesan**, **produksi**, dan **kirim** tetap terpisah. Terdapat tiga jadwal standar dan dapat ditambah jika diperlukan:
1. Kirim **subuh** → produksi sekitar 20.00 malam sebelumnya sampai subuh.
2. Kirim **pagi sekitar 08.00** → produksi subuh sampai 08.00.
3. Kirim **siang** → produksi 08.00–10.00.
SOP mengatur waktu dan eksekusi; middleware menyimpan asosiasi jadwal dan tanggal, **bukan scheduler kegiatan dapur**. Tanggal administratif produksi lintas tengah malam belum dikonfirmasi.

## 6. Konsolidasi MO produk jadi
- Konsolidasi lintas tujuh toko berdasarkan **SKU × dapur produksi × tanggal produksi × jadwal produksi** (dan terikat jadwal/tanggal kirim terkait).
- Simpan terpisah: `qty_requested` (asli agregat toko), `qty_planned` (dapat direvisi Admin Produksi), `qty_mo` (kelipatan BoM).
- Kuantitas target: `qty_mo = ceil(qty_planned / bom_output_qty) * bom_output_qty` untuk qty_planned > 0.
- **qty_mo ≤ kapasitas SKU per jadwal**. SOP telah menetapkan kapasitas dengan pertimbangan kelipatan batch; middleware tetap validasi. Perlakuan saat tidak muat masih perlu aturan final, jangan diam-diam memotong atau memindahkan jadwal.
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
- Finalisasi tanggal administratif produksi saat melewati tengah malam.
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
