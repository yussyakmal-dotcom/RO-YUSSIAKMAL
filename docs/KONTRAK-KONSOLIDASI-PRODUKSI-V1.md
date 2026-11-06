# Kontrak Bisnis Konsolidasi Produksi V1

**Tanggal pembaruan:** 2026-11-06  
**Status:** Kontrak bisnis dengan **implementasi Konsolidasi Produksi V1 tahap awal**. MO/BoM/transfer Odoo masih belum tersedia.  
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
| Produk B | 500 Pcs | 400 Pcs | **400 Pcs — boleh disimpan, kekurangan 100 Pcs** |

- **DISEPAKATI (2026-11-06):** Bila Qty Pesan **500 Pcs**, kapasitas tersedia **400 Pcs**, dan Admin Produksi menetapkan **Qty Produksi 400 Pcs**, **rencana konsolidasi boleh disimpan**. Catat **kekurangan permintaan 100 Pcs** secara eksplisit; jangan memaksa Qty Produksi = Qty Pesan dan jangan memindahkan 100 Pcs ke jadwal kirim lain. Status pekerjaan perencanaan tidak boleh ditafsirkan sebagai pemenuhan 500 Pcs.
- Bila kapasitas belum diatur di master, tampilkan **`Kapasitas belum diatur`**, bukan **0** atau **tidak terbatas**.
- Data `ProductCapacity` saat ini unik untuk **SKU × Schedule** tanpa kolom tanggal/dapur. Jadwal pada kapasitas **harus ditafsirkan sebagai jadwal produksi** dalam fitur ini, bukan jadwal kirim. Perlu validasi konfigurasi jadwal production di tenant sebelum dipakai untuk menghitung keputusan.
- **USULAN keselamatan:** bila beberapa rencana memakai SKU yang sama pada **tanggal + jadwal produksi** sama, tampilkan juga **kapasitas yang sudah terpakai di rencana lain / kapasitas tersisa**. Jangan menjanjikan kapasitas penuh kepada dua rencana yang berbeda pada slot produksi yang sama.
- **DISEPAKATI:** Qty Produksi **boleh lebih rendah daripada Qty Pesan akibat keterbatasan kapasitas**, dan penyimpanan konsolidasi **tidak boleh ditolak hanya karena ada kekurangan** selama seluruh validasi lainnya terpenuhi. Selisih wajib tersimpan pada rincian rencana dan terlihat di UI/histori.
- **Perhitungan terpisah:** `qty_shortfall = max(0, qty_requested - qty_planned)` menunjukkan kebutuhan pesanan **yang belum tercakup rencana**, sedangkan `capacity_gap = max(0, qty_requested - capacity_available)` menunjukkan kebutuhan yang **melampaui kapasitas tersedia**. Keduanya tidak selalu sama (mis. diminta 500, kapasitas 400, direncanakan 350 → shortfall 150 dan capacity gap 100).
- **TERBUKA:** apakah Qty Planned boleh **0** atau lebih besar daripada Qty Pesan, siapa menyetujui kekurangan, bagaimana kekurangan dialokasikan ke toko saat distribusi, status tindak lanjut kekurangan, serta apakah Qty Planned melebihi kapasitas dapat disimpan. **Jangan otomatis mengizinkan Qty Planned > kapasitas** dari keputusan ini. PRD tetap menetapkan `qty_mo <= kapasitas`; pembuatan MO di tahap berikutnya wajib menguji ulang hasil pembulatan BoM dan tidak otomatis lolos hanya karena konsolidasi sudah disimpan.
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
5. **Simpan Konsolidasi** (fitur berikutnya) harus mengizinkan Qty Produksi di bawah Qty Pesan ketika kapasitas tidak cukup, **menyimpan Qty Pesan/Produksi/Kapasitas dan kekurangannya**, serta mempertahankan jadwal kirim toko. Ketentuan lain yang belum diputuskan tetap divalidasi secara konservatif.

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
6. Bila Qty Pesan 500 Pcs dan kapasitas tersedia 400 Pcs, Admin Produksi dapat menyimpan Qty Produksi 400 Pcs dengan **Qty Kekurangan 100 Pcs tersimpan dan terlihat** dalam form/histori; 500 Pcs beserta jadwal kirim toko tetap tidak berubah.
7. Qty terformat integer per UoM dan sumber toko terlacak; tidak ada Qty pecahan diteruskan untuk produksi.
8. Relasi sumber tidak memungkinkan konsolidasi ganda walau dua operator mengirim pada waktu sama.
9. Bila simpan berhasil, baru sumber terkait berubah menjadi PROSES_PRODUKSI; simpan gagal tidak meninggalkan rencana/status parsial.
10. Tindakan pratinjau/Lihat Rekap tidak menulis ke DB/Odoo; endpoint terproteksi berdasarkan role.
11. Regresi PostgreSQL, Django API, frontend, kapasitas dan concurrency lulus CI serta dokumentasi PRD/README/Decision Log sinkron.

## 9. Keputusan terbuka sebelum coding **penyimpanan**

- **Q-1:** Apakah satu *kelompok permintaan pengiriman yang sama* boleh sengaja diproduksi dalam beberapa jadwal produksi dengan alokasi eksplisit, atau selalu satu jadwal produksi per kelompok SKU? **Tidak boleh memecah jadwal pengiriman** dalam kedua pilihan.
- **Q-2 (SEBAGIAN TERJAWAB):** **DISEPAKATI** simpan Qty Produksi 400 Pcs saat Qty Pesan 500 Pcs dan kapasitas tersedia 400 Pcs; kekurangan 100 Pcs harus tercatat. **TERBUKA** aturan untuk Qty Produksi **melebihi kapasitas**, kapasitas tidak terkonfigurasi, approval selisih, dan mekanisme tindak lanjut kekurangan.
- **Q-3:** Apakah Qty Produksi awal diisi sama dengan Qty Pesan atau kosong, bolehkah nol/lebih tinggi/lebih rendah, dan penanganan selisih?
- **Q-4:** Jadwal produksi mana yang valid di master `Schedule`, apakah perlu tabel khusus jadwal produksi, serta sumber aturan kapasitas jika SKU/dapur/shift sama dipakai beberapa rencana.
- **Q-5:** Aturan pesanan terlambat, revisi/pembatalan, serta batas tanggal produksi relatif terhadap tanggal kirim.

**Gerbang implementasi:** keputusan yang sudah eksplisit dalam dokumen ini harus mengikat, tetapi item **TERBUKA** tidak boleh dijawab dengan asumsi tersembunyi. Perubahan skema dan aksi penyimpanan akan dibuat pada PR terpisah, dengan migrasi aman atas data yang ada dan validasi bersama operator.

## 10. Keputusan terbaru: rencana dengan kekurangan kapasitas boleh disimpan (2026-11-06)

**DISEPAKATI:** Tiga angka wajib tampil bersamaan: **Qty Pesan 500 Pcs**, **Kapasitas Produksi 400 Pcs**, **Qty Produksi 400 Pcs**. Sistem menyimpan rencana meskipun kebutuhan 100 Pcs **belum tercakup**, dan menyimpan `qty_shortfall=100` yang tetap terlihat dalam histori, peringatan, dan rencana.

- **Qty Pesan / jadwal kirim** tetap milik Admin Toko dan **tidak berubah**.
- **Qty Produksi** adalah keputusan Admin Produksi, bukan janji bahwa semua pesanan toko telah terpenuhi.
- **Kekurangan** harus dapat ditelusuri ke lingkup kirim dan SKU/UoM yang sama. Belum boleh dianggap sebagai pembatalan pesanan, perubahan jadwal kirim, atau tambahan MO otomatis.
- **Status `PROSES_PRODUKSI`** jika nantinya diaktifkan berarti pesanan **telah masuk proses perencanaan**, **bukan** seluruh permintaan telah diproduksi/dipenuhi. Detail Qty kekurangan harus tetap terlihat.
- Perhitungan tidak boleh mencampur UoM, tidak boleh menghasilkan desimal operasional, dan tidak boleh membuat alokasi per toko secara asumtif. **TERBUKA:** bagaimana 100 Pcs kekurangan dialokasikan per toko / diproses pada tahap Packing dan apakah perlu status penyelesaian khusus.
- Pengujian implementasi wajib memastikan save berhasil untuk 500/400/400, snapshot Qty dan shortage bertahan setelah reload, status sumber tidak berubah sebelum transaksi berhasil, dan jadwal pengiriman tetap SUBUH.

**Batas saat ini:** dokumen ini **bukan** implementasi form/API simpan konsolidasi. Tahap tersebut tetap memerlukan migrasi aman pemisahan jadwal produksi, relasi sumber, validasi kapasitas efektif, dan pengujian transaksi.

## 11. Implementasi Konsolidasi Produksi V1 (2026-11-06)

**Fitur yang diimplementasikan:**
- `ProductionPlan.production_date` diisi manual; `ProductionPlan.production_schedule` eksplisit dan berbeda dari `delivery_schedule` (hasil rename kolom lama `schedule`, sehingga data historis jadwal **kirim** tetap utuh).
- `GET /api/v1/production/consolidation/preview/` menerima `kitchen_code`, `delivery_date`, `delivery_schedule_code`, opsional `production_date` dan `production_schedule_code`. Hanya agregasi pesanan **KIRIM**, bukan PROSES_PRODUKSI; respons menampilkan Qty Pesan, kapasitas master, kapasitas terpakai dan tersisa, serta sumber toko.
- `POST /api/v1/production/consolidations/` menerima lingkup, **tanggal dan jadwal produksi eksplisit**, `order_ids` hasil pratinjau, dan `items[{product_id,qty_planned}]`. Validasi server mengunci pesanan dan baris kapasitas, memeriksa ulang scope dan Qty, lalu menyimpan rencana, snapshot pesanan sumber, Qty kapasitas master/terpakai/kekurangan, AuditLog, serta status `KIRIM → PROSES_PRODUKSI` **dalam satu transaksi**. Permintaan ulang ditolak sebagai konflik, bukan membuat dua rencana.
- `GET /api/v1/production/consolidations/{plan_id}/` menampilkan kembali rencana tersimpan beserta **kekurangan per SKU** dan asal toko. Inbox menyertakan `plan_id` sehingga tersedia aksi **Lihat Rencana**.
- Di `/produksi/` ada aksi **Rencanakan** pada pesanan KIRIM, form penuh (bukan modal rekap), tabel **Qty Pesan | Kapasitas | Terpakai | Tersisa | Qty Produksi | Kekurangan**. Lihat Rekap tetap pop-up baca-saja.
- `ProductionPlanLine.qty_mo` dan `batch_qty` sekarang boleh `NULL` (berarti **belum dihitung**, bukan Qty palsu). `capacity_qty` merekam master, `capacity_used_before` merekam penggunaan pada slot itu sebelum rencana baru, `qty_shortfall` merekam selisih pesan-produksi.
- `ProductionPlanSource.order` mempunyai relasi satu-ke-satu untuk anti-konsolidasi-ganda dan `lines_snapshot` menyimpan Qty/nama/SKU/UoM sumber. Constraint unik parsial menjaga satu scope pengiriman untuk rencana **baru**, sementara rencana historis dengan production_schedule NULL **tidak diberi slot tebakan** dan harus direkonsiliasi bila bentrok.

**Batas aman sementara (aturan ini bukan keputusan bisnis permanen):**
- Qty Produksi harus bilangan bulat **minimal 1**, tidak boleh melampaui **Qty Pesan** atau **kapasitas tersisa** pada tanggal dan jadwal produksi yang dipilih. Qty lebih rendah dari permintaan **diizinkan**, kekurangan tersimpan dan terlihat.
- **Kapasitas master belum diatur ⇒ tidak boleh simpan**, bukan diasumsikan nol atau tanpa batas. Kapasitas sudah dipakai oleh rencana lain pada tanggal + jadwal produksi yang sama ikut dikurangkan, menggunakan lock record ProductCapacity saat transaksi.
- Satu kelompok `dapur × tanggal kirim × jadwal kirim` hanya boleh mempunyai **satu rencana V1**; belum ada split ke beberapa jadwal produksi untuk *kelompok kirim yang sama*. Kelompok pengiriman berbeda boleh menggunakan SKU sama pada tanggal produksi sama dalam jadwal produksi berbeda.
- Tanggal produksi **tidak diberi default otomatis** atau aturan batas tanggal kirim yang belum disepakati. Jadwal produksi dipilih eksplisit dari master Schedule yang aktif (master yang sama, FK terpisah).
- `PROSES_PRODUKSI` berarti sudah masuk rencana dan **bukan** pemenuhan total kebutuhan; Qty Kekurangan harus tetap terlihat. Belum ada re-open, perubahan Qty rencana pascasimpan, aksi pengisian kekurangan ke toko, MO, BoM, kapasitas setelah pembulatan batch, atau Odoo write.

**Acceptance test tambahan:** 500 Pcs requested + 400 Pcs capacity + 400 Pcs planned ⇒ plan tersimpan, shortage 100, order toko tetap SUBUH 500, prod schedule terpisah, MO/batch NULL; replay/overcapacity/missing-capacity/Qty pecahan ditolak tanpa rencana parsial, history menampilkan shortage.
