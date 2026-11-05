# Kontrak Bisnis Konsolidasi Produksi V1

**Tanggal pembaruan:** 2026-11-06  
**Status:** Rancangan kontrak bisnis untuk implementasi berikutnya; **belum ada fitur simpan konsolidasi**.  
**Sumber keputusan:** pembahasan pemisahan tanggal/jadwal produksi dari tanggal/jadwal kirim, larangan memecah komitmen pengiriman toko, dan kewajiban menampilkan kapasitas produksi.

Istilah: **DISEPAKATI** berarti keputusan eksplisit operasional; **USULAN** berarti rekomendasi rancangan yang belum disahkan; **TERBUKA** berarti keputusan bisnis masih diperlukan.

## 1. Empat dimensi waktu yang berbeda

| Dimensi | Pemilik / asal | Aturan |
|---|---|---|
| **Tanggal Kirim** (`delivery_date`) | Admin Toko, pada `StoreOrder` | **DISEPAKATI:** tetap mengikuti permintaan toko |
| **Jadwal Kirim** (`delivery_schedule`) | Admin Toko, `StoreOrder.schedule` | **DISEPAKATI:** tidak boleh diubah/dipecah oleh Admin Produksi |
| **Tanggal Produksi** (`production_date`) | Admin Produksi | **DISEPAKATI:** dipilih **manual**, tidak otomatis H-1/H-2 |
| **Jadwal Produksi** (`production_schedule`) | Rencana produksi | **DISEPAKATI:** identitas yang **berbeda dari jadwal kirim** dan harus tersimpan bersama tanggal produksi |

**Pemisahan domain:** `SUBUH` pada pesanan toko adalah **jadwal pengiriman**. Jadwal produksi menyatakan waktu/slot pelaksanaan kerja dapur. Pemilihan jadwal produksi tidak boleh secara terselubung mengubah jadwal kirim toko.

**Contoh komitmen pengiriman:** Toko mengirim permintaan SKU X **500 Pcs** untuk **SUBUH** pada tanggal kirim 2026-11-07. Admin Produksi **tidak berhak** membuat permintaan itu menjadi **250 Pcs SUBUH + 250 Pcs PAGI**. Bila terjadi keterbatasan produksi, tampilkan selisih/kendala dan jalankan aturan penanganan kekurangan yang disetujui; jangan pindah jadwal kirim secara otomatis.

**Kemungkinan yang sah:** SKU X bisa diproduksi pada **tanggal produksi yang sama tetapi pada jadwal produksi yang berbeda** untuk memenuhi **kelompok permintaan pengiriman yang memang berbeda**. Dua rencana produksi tersebut tidak boleh ditimpa atau disatukan hanya karena tanggal dan SKU sama. **USULAN V1:** jangan membagi **satu kelompok permintaan pengiriman** ke beberapa jadwal produksi tanpa aturan alokasi dan persetujuan terpisah. Ini berbeda dari melarang SKU muncul dalam beberapa jadwal produksi untuk kelompok pengiriman yang berbeda.

## 2. Bentuk data yang ditargetkan

### ProductionPlan — header

**Skema yang diinginkan:** `kitchen`, `delivery_date`, `delivery_schedule`, `production_date`, `production_schedule`, `status`.

- `delivery_schedule`: jadwal kirim dari pesanan toko, **read-only** dari lingkup permintaan.
- `production_date`: tanggal produksi **dipilih manual**.
- `production_schedule`: jadwal produksi **tersendiri** yang tidak disamakan dengan jadwal kirim.
- `ProductionPlan` perlu **hubungan eksplisit ke sumber StoreOrder** agar permintaan tidak dihitung dua kali. Rincian sumber Qty per SKU/toko/UoM perlu dapat dilacak.

**Audit model saat ini:** `ProductionPlan` telah mempunyai `production_date`, `delivery_date`, dan satu FK `schedule`. FK itu **belum membedakan** jadwal kirim versus jadwal produksi. Constraint unik saat ini `(kitchen, production_date, delivery_date, schedule)` **belum mencakup production_schedule**; SKU yang diproduksi di beberapa jadwal pada hari sama tidak terwakili oleh identitas rencana yang lengkap.

**Rencana perubahan skema (USULAN teknis; belum dibuat migrasinya):**
1. Mempertahankan referensi jadwal kirim yang ada (migrasi penamaan menjadi `delivery_schedule` bila aman) dan menambah `production_schedule` sebagai FK eksplisit.
2. Identitas header dirancang dengan **dapur + tanggal kirim + jadwal kirim + tanggal produksi + jadwal produksi**; pencegahan alokasi ganda **tidak boleh hanya mengandalkan constraint header**.
3. Tambah relasi rencana ↔ StoreOrder dan pengamanan per **StoreOrderLine/produk** agar Qty sumber tidak tercatat di dua rencana tanpa alokasi yang sah.
4. Data historis `ProductionPlan` yang mungkin sudah ada perlu diaudit: **jangan otomatis mengisi jadwal produksi sama dengan jadwal kirim**.
5. `ProductionPlanLine` saat ini sudah memiliki `qty_requested`, `qty_planned`, `capacity_qty`, `qty_mo`, `batch_qty`; jangan mengisi `qty_mo`/`batch_qty` dengan angka palsu hanya untuk memungkinkan penyimpanan rencana awal.

## 3. Tiga angka wajib di layar Admin Produksi

Setiap baris SKU dalam workspace perencanaan **wajib** memperlihatkan **secara berdampingan**:

| Kolom | Sumber | Hak perubahan |
|---|---|---|
| **Qty Pesan / Qty Requested** | Total permintaan SKU+UoM dari StoreOrder **KIRIM** pada tanggal/jadwal kirim dan dapur yang dipilih | **Read-only**; tidak boleh diubah Admin Produksi |
| **Qty Kapasitas Produksi** | Master `ProductCapacity.max_qty` untuk `product × production_schedule` | Read-only; bukan angka rekaan atau hasil penjumlahan pesanan |
| **Qty Produksi / Qty Planned** | Diputuskan Admin Produksi untuk SKU dan rencana yang dituju | Dapat diedit di workspace perencanaan; tervalidasi dan diaudit saat penyimpanan |

**Contoh ilustratif (bukan angka dari tenant):**

| SKU | Qty Pesan | Kapasitas | Qty Produksi |
|---|---:|---:|---:|
| Produk A | 500 Pcs | 600 Pcs | 500 Pcs |
| Produk B | 500 Pcs | 400 Pcs | Belum ditetapkan |

- Bila Qty Pesan **lebih besar daripada kapasitas**, tampilkan **peringatan kapasitas/selisih**. Jangan otomatis memindahkan 100 Pcs ke jadwal kirim lain.
- Bila kapasitas belum diatur di master, tampilkan **`Kapasitas belum diatur`**, bukan **0** atau **tidak terbatas**.
- Data `ProductCapacity` saat ini unik untuk **SKU × Schedule** tanpa kolom tanggal/dapur. Jadwal pada kapasitas **harus ditafsirkan sebagai jadwal produksi** dalam fitur ini, bukan jadwal kirim. Perlu validasi konfigurasi jadwal production di tenant sebelum dipakai untuk menghitung keputusan.
- **USULAN keselamatan:** bila beberapa rencana memakai SKU yang sama pada **tanggal + jadwal produksi** sama, tampilkan juga **kapasitas yang sudah terpakai di rencana lain / kapasitas tersisa**. Jangan menjanjikan kapasitas penuh kepada dua rencana yang berbeda pada slot produksi yang sama.
- **TERBUKA:** apakah Qty Produksi boleh lebih rendah dari Qty Pesan dan bagaimana mengelola kekurangan; apakah boleh 0; peraturan approval bila selisih terjadi; apakah kebijakan kapasitas berlaku ke Qty Planned atau baru `qty_mo` hasil pembulatan BoM. PRD saat ini menetapkan `qty_mo <= capacity`; implementasi harus tetap memeriksa batas setelah pembulatan BoM pada tahap MO.
- **Belum termasuk** otomatisasi pembagian Qty ke slot produksi lain; aturan tersebut tidak boleh diimplikasikan dari adanya dua field jadwal.

## 4. Ruang lingkup konsolidasi dan status

- Calon konsolidasi berasal dari `StoreOrder.status=KIRIM`, dikelompokkan menurut **dapur + tanggal kirim + jadwal kirim**. `DRAFT`, `NO_ORDER`, dan `PROSES_PRODUKSI` bukan kandidat baru.
- Rekap baca-saja boleh tetap menampilkan `KIRIM` dan `PROSES_PRODUKSI`; **pratinjau konsolidasi baru harus hanya KIRIM** agar tidak mengonsolidasi order dua kali.
- Qty Requested adalah agregasi per **SKU+UoM** dengan asal toko, ID order, dan Qty asli tetap tersimpan.
- Qty Planned tidak boleh mengubah Qty Requested maupun jadwal kirim toko.
- **USULAN V1:** satu kelompok komitmen pengiriman untuk satu SKU tidak dipecah ke beberapa jadwal produksi; SKU yang sama tetap boleh berada di **dua rencana** untuk kelompok pengiriman berbeda, walaupun tanggal produksinya sama.
- **TERBUKA:** apakah satu kelompok pengiriman dapat sengaja diproduksi pada beberapa tanggal/jadwal produksi dengan model *allocation* terpisah, tanpa mengubah komitmen pengiriman. Jangan mengasumsikan split ini tersedia.
- **TERBUKA:** pesanan KIRIM terlambat setelah rencana tersimpan, revisi/perubahan produksi, dan pembatalan.

## 5. Pengamanan Qty dan UoM

- Semua Qty operasional ditampilkan sebagai bilangan bulat yang jelas; `1.0000` → `1`; `1232.0000` → `1.232`.
- UoM asli dari `Product.uom` (master Odoo); fallback **pcs** hanya bila kosong. Jangan menjumlahkan `Kg` dan `gram` sebagai bilangan tanpa satuan.
- Qty historis yang benar-benar pecahan atau tidak valid **memblokir simpan**; tidak ada pembulatan tersembunyi.
- Multi-UoM untuk **SKU yang sama** belum didukung skema `StoreOrderLine` saat ini; implementasi perlu aturan konversi terverifikasi dan relasi UoM per baris sebelum diperbolehkan.

## 6. Alur UI yang ditargetkan (belum tersedia)

1. Admin Produksi melihat seluruh pesanan KIRIM / PROSES PRODUKSI dalam antrean global. Tombol **Lihat Rekap** tetap membuka modal baca-saja, lalu kembali fokus ke antrean.
2. Tindakan terpisah **Rencanakan/Konsolidasi Produksi** membuka workspace yang menampilkan **tanggal kirim + jadwal kirim** secara read-only dan field **tanggal produksi + jadwal produksi** secara eksplisit.
3. Tabel SKU memuat **Qty Pesan | Qty Kapasitas Produksi | Qty Produksi**, beserta UoM, kapasitas terpakai/tersisa bila relevan, dan peringatan selisih.
4. **Pratinjau** tetap read-only terhadap database; perubahan Qty Produksi dalam formulir lokal belum mengubah order, status atau Odoo.
5. **Simpan Konsolidasi** (fitur berikutnya) baru boleh aktif sesudah validasi lengkap dan aturan penanganan kapasitas ditetapkan.

## 7. Transaksi, anti-duplikasi dan audit

Persyaratan implementasi saat simpan:
- Simpan ProductionPlan, ProductionPlanLine, relasi eksplisit rencana ↔ StoreOrder/StoreOrderLine, snapshot Qty+UoM sumber, AuditLog, dan transisi `KIRIM → PROSES_PRODUKSI` **secara atomik**.
- Kunci semua sumber saat konsolidasi, validasi ulang status KIRIM dan lingkup tanggal/jadwal kirim yang tidak berubah; tolak konflik bila sumber sudah dikonsolidasi.
- Permintaan 500 SUBUH tetap disimpan **500 SUBUH** sebagai komitmen; Qty Produksi boleh berbeda hanya sesuai aturan selisih/kekurangan yang disetujui, bukan perubahan order toko.
- Sebuah SKU boleh ada pada produksi tanggal sama dengan jadwal produksi berbeda **tanpa menggandakan Qty sumber**.
- Kapasitas dipantau per SKU/jadwal produksi dan potensi penggunaan oleh rencana lain; jangan menilai kapasitas hanya berdasarkan satu request tanpa melihat rencana yang sudah ada.
- Audit minimal actor, timestamp, tanggal/jadwal produksi, tanggal/jadwal kirim, seluruh ID sumber dan Qty Requested/Planned/Capacity, perubahan status, dan alasan perubahan bila nanti SOP menetapkan.
- Hanya Group PRODUCTION/ADMIN dan superuser boleh melakukan simpan; STORE tidak.
- Membuka rekap/pratinjau tidak mengubah database atau Odoo. Bila salah satu tahap simpan gagal, seluruh transaksi dibatalkan.

## 8. Kriteria penerimaan implementasi

1. Pesanan T_BAN #1 dan T_KD #2 pada **JP / 2026-11-07 / SUBUH** tersedia sebagai kandidat bila masih KIRIM.
2. Form menunjukkan tanggal/jadwal **kirim** tanpa bisa diubah, serta tanggal produksi yang harus dipilih operator dan **jadwal produksi tersendiri**.
3. Satu SKU bisa terdaftar pada **dua jadwal produksi di tanggal produksi sama** ketika sumber permintaan memang terpisah, tanpa menimpa rencana lainnya.
4. Order **500 Pcs SUBUH** tidak berubah otomatis menjadi 250 SUBUH + 250 PAGI, atau dipindahkan jadwal kirim akibat kapasitas.
5. Per SKU menampilkan **Qty Pesan, Qty Kapasitas Produksi, Qty Produksi**; master kapasitas yang belum ada tidak direkayasa menjadi nol/tidak terbatas.
6. Bila Qty Pesan 500 dan kapasitas 400, sistem menunjukkan kekurangan secara eksplisit, tanpa memecah atau mengalihkan jadwal kirim.
7. Qty terformat integer per UoM dan sumber toko terlacak; tidak ada Qty pecahan diteruskan untuk produksi.
8. Relasi sumber tidak memungkinkan konsolidasi ganda walau dua operator mengirim pada waktu sama.
9. Bila simpan berhasil, baru sumber terkait berubah menjadi PROSES_PRODUKSI; simpan gagal tidak meninggalkan rencana/status parsial.
10. Tindakan pratinjau/Lihat Rekap tidak menulis ke DB/Odoo; endpoint terproteksi berdasarkan role.
11. Regresi PostgreSQL, Django API, frontend, kapasitas dan concurrency lulus CI serta dokumentasi PRD/README/Decision Log sinkron.

## 9. Keputusan terbuka sebelum coding **penyimpanan**

- **Q-1:** Apakah satu *kelompok permintaan pengiriman yang sama* boleh sengaja diproduksi dalam beberapa jadwal produksi dengan alokasi eksplisit, atau selalu satu jadwal produksi per kelompok SKU? **Tidak boleh memecah jadwal pengiriman** dalam kedua pilihan.
- **Q-2:** Aturan ketika `Qty Pesan > Kapasitas` atau `Qty Produksi > Kapasitas`: blokir simpan atau simpan rencana dengan catatan kekurangan/approval?
- **Q-3:** Apakah Qty Produksi awal diisi sama dengan Qty Pesan atau kosong, bolehkah nol/lebih tinggi/lebih rendah, dan penanganan selisih?
- **Q-4:** Jadwal produksi mana yang valid di master `Schedule`, apakah perlu tabel khusus jadwal produksi, serta sumber aturan kapasitas jika SKU/dapur/shift sama dipakai beberapa rencana.
- **Q-5:** Aturan pesanan terlambat, revisi/pembatalan, serta batas tanggal produksi relatif terhadap tanggal kirim.

**Gerbang implementasi:** keputusan yang sudah eksplisit dalam dokumen ini harus mengikat, tetapi item **TERBUKA** tidak boleh dijawab dengan asumsi tersembunyi. Perubahan skema dan aksi penyimpanan akan dibuat pada PR terpisah, dengan migrasi aman atas data yang ada dan validasi bersama operator.
