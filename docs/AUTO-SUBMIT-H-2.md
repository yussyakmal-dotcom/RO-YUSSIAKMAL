# Auto-submit Draft H-2 pukul 07.00 WIB

**Status:** perintah backend dan template timer Debian sudah dibuat; **timer belum aktif pada server pengguna** sampai dipasang dan di-enable secara manual.

## Aturan bisnis

- Setiap **07.00 WIB** pada tanggal **H-2** dari `delivery_date`, seluruh **StoreOrder status DRAFT yang sudah ada** untuk tanggal pengiriman tersebut difinalisasi.
- Pesanan dipisahkan menurut **toko × dapur × tanggal kirim × jadwal kirim**. Semua dapur dan jadwal diperiksa, bukan hanya satu kitchen.
- Hanya Qty bilangan bulat **≥ 1** yang ikut `KIRIM`. Baris Qty 0 dihapus, dan **Draft yang seluruh Qty nol/kosong menjadi `NO_ORDER`**.
- Setelah auto-submit, Qty pesanan terkunci. `auto_submitted=True`, `submitted_at` diisi waktu WIB, dan AuditLog mencatat `AUTO_KIRIM` atau `AUTO_NO_ORDER`, tanpa mengarang nama aktor.
- Pesanan yang **sudah KIRIM/NO_ORDER** sebelumnya tidak disentuh. Menjalankan lagi perintah tidak membuat duplikasi.
- **Tidak membuat order baru** untuk toko/dapur yang belum pernah menyimpan Draft; tidak menebak pesanan yang hilang. Tidak membuat MO/stock transfer dan **tidak menulis Odoo**.
- Draft lama dengan Qty desimal/negatif **dilewati** (tidak dibulatkan). Perintah menampilkan `invalid_order_ids` dan exit nonzero agar kegagalan terlihat pada log systemd. Pesanan valid yang lain tetap diproses dalam transaksi masing-masing.

## Verifikasi dulu (PREVIEW, tanpa menulis)

Setelah memperbarui container:

```bash
cd ~/RO-YUSSIAKMAL
git pull origin main
docker compose up -d --build --force-recreate api
docker compose exec api python manage.py auto_submit_store_orders
```

Perintah **tanpa `--apply`** hanya menampilkan JSON: tanggal bisnis WIB, tanggal pengiriman H+2 yang dituju, jumlah Draft yang ada, jumlah kandidat KIRIM/NO_ORDER, serta `invalid_order_ids`. Preview boleh dijalankan sebelum atau sesudah 07.00.

`--apply` **hanya boleh** pada/pasca 07.00 WIB tanggal H-2. Perintah sengaja menolak `--apply` sebelum 07.00 WIB. **Jangan jalankan `--apply` saat masih menguji data Draft** yang belum ingin difinalisasi.

## Aktifkan penjadwalan harian di Debian (setelah preview disetujui)

Tidak memerlukan Redis, Celery, atau container tambahan. Template systemd di repo:
- `deploy/systemd/ro-auto-submit@.service`
- `deploy/systemd/ro-auto-submit@.timer`

Unit disiapkan untuk akun Debian `feri` yang memiliki akses `docker compose` dan repository pada `/home/feri/RO-YUSSIAKMAL`. Jika user/path server berbeda, sesuaikan template sebelum pemasangan.

Dari root repository:

```bash
sudo cp deploy/systemd/ro-auto-submit@.service /etc/systemd/system/
sudo cp deploy/systemd/ro-auto-submit@.timer /etc/systemd/system/
sudo systemctl daemon-reload
systemd-analyze calendar '*-*-* 07:00:00 Asia/Jakarta'
sudo systemctl enable --now ro-auto-submit@feri.timer
systemctl list-timers --all 'ro-auto-submit*'
```

Timer bekerja **07:00 setiap hari menurut Asia/Jakarta**, walaupun zona waktu host Debian bukan WIB. Eksekusi menggunakan `docker compose exec -T api python manage.py auto_submit_store_orders --apply` agar tidak membutuhkan terminal/TTY.

**PENTING:** `Persistent=false`, jadi aktivasi pertama di atas **tidak langsung memproses Draft lama pada malam hari**. Jika server mati tepat pada jam cutoff, run terlewat dan operator harus meninjau pesanan secara manual. Jangan backdate atau memaksa pengiriman tanpa pemeriksaan operator.

Monitoring:

```bash
systemctl status ro-auto-submit@feri.timer
journalctl -u ro-auto-submit@feri.service -n 100 --no-pager
```

Untuk menghentikan otomatisasi jika diperlukan:

```bash
sudo systemctl disable --now ro-auto-submit@feri.timer
```

Jika butuh uji manual setelah 07 WIB, gunakan **preview terlebih dahulu**. Setelah memeriksa kandidat, menjalankan `docker compose exec api python manage.py auto_submit_store_orders --apply` akan benar-benar mengunci seluruh Draft eligible. Ini bukan simulasi.

## Batas V1 yang harus diperhatikan

- **Timer tidak diaktifkan oleh `docker compose up`.** Hanya `systemctl enable --now` yang memasang jadwal.
- Penggunaan jadwal otomatis harus dikonfirmasi setelah operator memverifikasi data Draft nyata dan kebijakan tanggal.
- **Input Draft baru atau perubahan Draft setelah jam cutoff** belum dibatasi oleh API toko pada V1 ini. Draft yang disimpan **setelah** run 07.00 tidak akan tertangkap oleh run harian yang sudah selesai. **Ini perlu keputusan dan pengamanan lanjutan** (misalnya batas input setelah 07.00 dan perubahan default tanggal pengiriman) sebelum proses dipakai untuk operasional tanpa pengawasan.
- Jika timer terlewat saat server mati, V1 tidak otomatis menyisir backlog beberapa hari. Butuh prosedur koreksi operator.
- Proses tidak menyentuh Odoo, tidak mengubah jadwal pengiriman/produksi, dan tidak mengubah master template SKU.
- Tidak ada migration database; `StoreOrder.auto_submitted` dan `submitted_at` sudah tersedia sebelumnya.
