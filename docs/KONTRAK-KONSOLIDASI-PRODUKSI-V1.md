# Kontrak Bisnis Konsolidasi Produksi V1

**Tanggal keputusan:** 2026-11-06  
**Status:** **Kontrak rancangan / untuk review**, belum menjadi fitur yang dapat dijalankan.  
**Ruang lingkup:** RO Middleware, Admin Produksi, konsolidasi kebutuhan pesanan toko ke **rencana produksi lokal PostgreSQL**. **Bukan** pembuatan MO/transfer Odoo.  
**Keputusan eksplisit disepakati:** **tanggal produksi dipilih manual oleh Admin Produksi**, tidak dihitung H-1/H-2 atau ditebak berdasarkan jadwal kirim. Hal lain yang belum diputuskan ditandai **USULAN** atau **TERBUKA**.

## 1. Tujuan dan batas

Mengubah kumpulan pesanan toko **KIRIM** menjadi satu **ProductionPlan** yang memiliki daftar SKU dan kuantitas rencana yang dapat ditelusuri ke pesanan asalnya. Setelah konsolidasi berhasil disimpan, pesanan sumber berubah menjadi **PROSES_PRODUKSI**.

Tahap V1 ini belum membuat MO, tidak membulatkan BoM, belum menghitung stok bahan/capacity efektif, tidak membuat transfer, dan **tidak menulis ke Odoo**. Semua fitur Odoo lanjutannya harus menggunakan rencana tersimpan, bukan menafsirkan ulang Qty toko.

## 2. Identitas permintaan dan tanggal

| Field | Sumber / makna | Status |
|---|---|---|
| **Dapur** | `StoreOrder.kitchen` | Sudah ada, wajib |
| **Tanggal kirim** | `StoreOrder.delivery_date` | Sudah ada, wajib |
| **Jadwal kirim** | `StoreOrder.schedule` | Sudah ada, wajib |
| **Tanggal produksi** | Diisi **manual** oleh Admin Produksi pada formulir konsolidasi, disimpan sebagai `ProductionPlan.production_date` | **DISEPAKATI** |
| **Jadwal produksi** | Jadwal operasional produksi, **bukan otomatis jadwal kirim** | **TERBUKA**: model `ProductionPlan` saat ini hanya memiliki `schedule` untuk jadwal kirim |

**Aturan tanggal produksi yang disepakati:**
- Harus ditampilkan sebagai field eksplisit dan **wajib dipilih sebelum Simpan Konsolidasi**. Tidak diisi otomatis dari H-1/H-2, tanggal kirim, jam WIB, atau default sistem.
- Admin Produksi melihat sekaligus **tanggal kirim**, **jadwal kirim**, dan **tanggal produksi** agar tidak tertukar.
- Untuk `JP / SUBUH / kirim 2026-11-07`, contoh tanggal produksi yang mungkin dimasukkan operator adalah `2026-11-06` **atau** `2026-11-07`; **tidak satu pun menjadi default otomatis**.
- **TERBUKA**: apakah tanggal produksi boleh sesudah tanggal kirim, batas mundur/maju yang diperbolehkan, kebutuhan approval lintas tengah malam, serta apakah satu lingkup pengiriman boleh dibagi ke **lebih dari satu tanggal produksi**. Jangan memasang aturan tanggal diam-diam.

**Lingkup konsolidasi awal (USULAN V1):** satu kelompok `dapur × tanggal kirim × jadwal kirim` yang diserahkan oleh toko, lalu Admin Produksi memilih tanggal produksi untuk kelompok tersebut. Pada versi ini **belum boleh membelah kelompok menjadi dua rencana tanggal berbeda** sampai kebijakan pemecahan lingkup ditetapkan.

## 3. Sumber data dan visibilitas

- Sumber **kandidat konsolidasi baru**: `StoreOrder.status == KIRIM` dengan dapur, tanggal kirim, jadwal kirim yang sama. Jangan mengambil `DRAFT`, `NO_ORDER`, atau belum membuat order.
- `PROSES_PRODUKSI` boleh tetap **terlihat dalam antrean/histori dan rekap baca-saja**; **tidak boleh dikonsolidasi ulang sebagai permintaan baru**.
- Qty toko final tidak boleh diubah melalui Admin Produksi. Semua perubahan rencana dilakukan pada kolom Qty Planned, bukan StoreOrderLine.
- Katalog SKU yang kini nonaktif tetap ikut bila sudah ada pada pesanan KIRIM historis. Sumber kebutuhan adalah baris pesanan final, bukan daftar template saat ini.
- Jika tidak ada pesanan `KIRIM` pada lingkup, **jangan buat ProductionPlan kosong**.
- **TERBUKA:** bagaimana memperlakukan pesanan **KIRIM yang datang terlambat** setelah rencana untuk lingkup sama sudah tersimpan; saat ini tidak boleh diam-diam dimasukkan ke rencana existing atau digandakan.

## 4. Alur operator (target UX, belum diimplementasikan)

1. Buka `/produksi/` dan lihat tab Semua / Kirim / Proses Produksi tanpa perlu menentukan tanggal terlebih dahulu.
2. Klik **Lihat rekap**: modal baca-saja yang sudah ada tetap berfungsi dan kembali fokus ke antrean setelah ditutup; **tidak mengubah status**.
3. Untuk kelompok pesanan KIRIM yang eligible, pilih tindakan terpisah **Buat Konsolidasi** (USULAN).
4. Halaman/form konsolidasi menampilkan dapur, tanggal kirim, jadwal kirim, daftar pesanan sumber dan SKU, **Qty Requested**, **Qty Planned** serta field **Tanggal Produksi** yang sengaja kosong sampai operator memilih.
5. **Pratinjau** tidak menulis database atau mengubah status. **Simpan Konsolidasi** memvalidasi ulang data server lalu menyimpan satu rencana beserta keterkaitan pesanan sumber.
6. Hanya **setelah seluruh transaksi berhasil**, setiap pesanan sumber yang dikonsolidasi berubah `KIRIM → PROSES_PRODUKSI`. Tampilan antrean memperbarui statusnya. Jika gagal, semua tetap `KIRIM`.

**USULAN:** tampilkan halaman kerja konsolidasi terpisah agar formulir ratusan SKU tidak membuat pop-up rekap terlalu penuh. Menutup rekap tetap mengembalikan fokus ke baris sebelumnya.

## 5. Kontrak Qty dan UoM

| Konsep | Aturan |
|---|---|
| **Qty Requested** | Hasil penjumlahan **SKU yang sama dalam UoM sama** dari pesanan KIRIM terpilih; tidak dapat diedit |
| **Qty Planned** | Keputusan Admin Produksi **per SKU**, tidak boleh mengganti Qty Requested asli |
| **Tampilan Qty** | Bilangan **bulat tanpa .0000**; pakai format ribuan Indonesia, misalnya `1.232 Pcs` |
| **UoM** | UoM asli master Odoo melalui `Product.uom`. Label `pcs` hanya fallback bila belum ada UoM |
| **UoM berbeda** | Jangan dijumlahkan menjadi angka yang tidak bermakna; subtotal tetap per UoM |
| **Qty pecahan historis** | **Blokir konsolidasi** dan beri pesan `Perlu koreksi Qty`; jangan membulatkan, menghilangkan digit, atau mengonversi diam-diam |
| **Multi UoM satu SKU** | **TERBUKA / belum didukung** oleh `StoreOrderLine` (unik per `order + product`). Contoh `1 Kg` dan `500 gram` sebagai dua baris memerlukan desain eksplisit berbasis UoM/konversi Odoo |

**USULAN untuk Qty Planned V1:** setiap SKU wajib memiliki Qty Planned integer nonnegatif; default formulir dapat menggunakan Qty Requested **hanya setelah disetujui**. Kebijakan boleh tidaknya Qty Planned = 0 untuk SKU yang diminta, alasan penurunan/kenaikan, dan kontrol kapasitas tahap ini **TERBUKA**.

Jangan mengimplementasikan `qty_mo = ceil(qty_planned / BoM output)` pada tombol simpan V1 ini. `ProductionPlanLine.qty_mo`, `batch_qty`, `capacity_qty`, dan `bom_snapshot` saat ini diwajibkan model; perlu keputusan nilai awal/skema dan pemisahan tahap sebelum boleh menyimpan rencana yang benar.

## 6. Keutuhan data, status, dan audit

**Persyaratan teknis wajib untuk implementasi berikutnya:**
- Simpan `ProductionPlan`, `ProductionPlanLine`, **relasi eksplisit rencana ↔ pesanan sumber**, snapshot Qty asal per SKU/toko/UoM yang relevan, AuditLog, dan transisi status `StoreOrder` dalam **satu transaksi PostgreSQL atomik**.
- Kunci baris `StoreOrder` sumber saat submit (`select_for_update`), verifikasi ulang semuanya masih `KIRIM`, memuat Qty integer valid, serta cocok dengan lingkup yang dipilih. Jika berubah sejak preview, tolak dengan konflik dan minta muat ulang.
- **Cegah pesanan masuk ke lebih dari satu rencana aktif**, termasuk jika Admin Produksi dua kali menekan Simpan atau dua pengguna konsolidasi bersamaan. Gunakan constraint DB atau mekanisme unik setara pada relasi sumber plus transaksi/idempotency key.
- Identitas audit minimal: actor/user, timestamp WIB, ID rencana, tanggal produksi manual, lingkup pengiriman, ID pesanan sumber, jumlah SKU, Qty Requested, Qty Planned, dan perubahan status.
- Satu kali membuka rekap, membuka formulir, atau menyimpan pratinjau **tidak boleh** mengubah status.
- Satu transaksi gagal berarti **tidak ada ProductionPlan parsial dan tidak ada pesanan yang telanjur PROSES_PRODUKSI**.
- Hanya Group `PRODUCTION`, `ADMIN`, dan superuser yang boleh konsolidasi; Group `STORE` tidak.
- Jangan mengubah pesanan toko yang sudah KIRIM; revisi rencana harus tetap terpisah dan teraudit.

**Kesenjangan model yang sudah diverifikasi:**
1. `ProductionPlan` memiliki `production_date`, `delivery_date`, `kitchen`, dan `schedule`; namun **belum memiliki relasi sumber ke StoreOrder**.
2. Constraint unik saat ini `(kitchen, production_date, delivery_date, schedule)`. Mengganti production_date dapat mengizinkan rencana kedua untuk **lingkup pengiriman dan pesanan yang sama**. Perlu pengamanan relasi dan keputusan apakah split produksi lintas tanggal diperbolehkan.
3. `ProductionPlanLine` mewajibkan `qty_mo`, `batch_qty`, `capacity_qty` serta snapshot. Untuk milestone konsolidasi awal, tidak boleh mengisi data tersebut dengan nilai dummy yang dapat dianggap hasil perencanaan kapasitas/BoM valid.
4. `production_demand` sekarang menampilkan gabungan `KIRIM + PROSES_PRODUKSI` untuk **rekap baca-saja**. Endpoint **kandidat konsolidasi baru** harus membedakan `KIRIM` saja agar tidak memasukkan permintaan yang sudah diproses.

## 7. Kriteria penerimaan sebelum dianggap selesai

1. Toko Bandara **Order #1** dan Kedaton **Order #2** dengan `JP / SUBUH / kirim 2026-11-07` muncul sebagai calon konsolidasi selama masih `KIRIM`.
2. Admin Produksi **harus memilih sendiri Tanggal Produksi**. Sistem tidak otomatis mengisi 6 atau 7 November.
3. SKU identik dari dua toko digabung menjadi **satu Qty Requested per SKU+UoM**, dengan rincian sumber dan Qty masing-masing toko tetap terlihat; total lintas UoM tidak dibuat.
4. Qty tampil integer (`1.0000` → `1`), data pecahan historis ditolak dengan pesan jelas dan tidak diubah.
5. Draft, NO_ORDER, dan order PROSES_PRODUKSI **tidak** menjadi sumber konsolidasi baru.
6. Pratinjau dan **Lihat rekap** tidak mengubah DB, status, atau Odoo.
7. Simpan berhasil menghasilkan rencana lengkap, relasi order sumber, audit, dan **baru kemudian** semua order sumber berstatus PROSES_PRODUKSI.
8. Simpan gagal/validasi gagal tidak menghasilkan rencana parsial atau perubahan status.
9. Pengiriman ulang request, dua operator bersamaan, atau penggantian tanggal produksi tidak menyebabkan satu StoreOrder masuk dua konsolidasi aktif.
10. Akses STORE/anonymous tidak bisa membaca pratinjau konsolidasi terproteksi ataupun melakukan simpan.
11. Aturan perubahan Qty Planned tidak memengaruhi Qty Requested atau pesanan toko; revisi teraudit dan tidak melewati tahap MO berikutnya.
12. Tidak ada write API Odoo di milestone ini; seluruh migrasi dan tes lulus pada PostgreSQL serta build React, dan dokumentasi tetap diperbarui.

## 8. Keputusan yang masih harus ditutup sebelum coding penyimpanan

**Prioritas 1 — memengaruhi struktur data:** apakah satu lingkup `dapur × tanggal kirim × jadwal kirim` **harus satu ProductionPlan saja**, atau bisa dibagi ke beberapa tanggal produksi. USULAN V1: **satu lingkup → satu rencana**, tanggal produksi dipilih manual sekali dan satu StoreOrder hanya tertaut ke satu rencana aktif.

**Prioritas 2 — validasi operator:** default Qty Planned (sama dengan Requested atau kosong), boleh tidaknya nilai 0, perubahan Qty Planned yang melebihi permintaan, dan approval.

**Prioritas 3 — definisi jadwal:** jadwal produksi berbeda dari jadwal kirim atau tidak, serta perlakuan produksi melewati tengah malam. Penentuan tanggal **sudah manual**, tetapi batas validasinya belum ditetapkan.

**Prioritas 4 — operasional pengecualian:** pesanan KIRIM terlambat setelah konsolidasi, pembatalan/reopen rencana, perubahan tanggal produksi setelah simpan, dan kebijakan ketika Qty melebihi kapasitas.

> **Gerbang implementasi:** hanya keputusan tanggal produksi manual yang telah disepakati dalam percakapan ini. Seluruh item bertanda **USULAN** dan **TERBUKA** adalah bahan review, bukan izin untuk menulis kode mutasi yang menyimpan ProductionPlan. Kontrak ini adalah target bisnis dan rencana desain; kode operasional sekarang masih rekap baca-saja.
