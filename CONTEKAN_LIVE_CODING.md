# 🛡️ CONTEKAN SAKTI LIVE CODING: RADIAL VAULT (RadialQR)
> **Simpan & buka file ini saat sesi live coding / interview Discord.**
> Proyek ini adalah sistem steganografi / visual encoding kustom berbasis lingkaran konsentris (*polar ring encoding*) yang dilengkapi enkripsi AES-Fernet, deteksi computer vision (OpenCV), dan redundansi koreksi eror.

---

## 🚀 1. ELEVATOR PITCH (Jawaban 30 Detik Kalau Ditanya "Jelasin Proyek Ini")
> *"RadialQR adalah format visual data encoder melingkar sebagai alternatif QR Code kotak konvensional. Data dikonversi ke bitstream biner (Hijau = 1, Merah = 0) dan dipetakan ke cincin konsentris dari dalam ke luar menggunakan koordinat polar ($r, \theta$).*
> 
> *Sistem ini punya fitur ketahanan tinggi: orientasi bebas putar 360° berkat **Anchor Ring** di cincin terdalam, verifikasi integritas **CRC-32**, auto kompresi **zlib**, serta **Redundansi 2 Salinan (Double-Copy Recovery)**. Selain itu, arsitektur v2-nya memisahkan kunci enkripsi (PNG) dan payload terenkripsi (.enc) untuk mencegah serangan single-file vault."*

---

## 🧩 2. BEDAH ANATOMI CINCIN (Struktur Gambar dari Dalam ke Luar)

| Cincin | Nama | Isi / Fungsi | Logika Penting |
| :--- | :--- | :--- | :--- |
| **Ring 0** *(r = 3.0)* | **Anchor Ring** | `[1, 0, 0, 0]` (1 Hijau, 3 Merah) | Sebagai **kompas rotasi**. Node hijau selalu menunjuk "Utara" (jam 12). Berapa pun gambar diputar, decoder akan mencari sudut node hijau ini untuk mengembalikan orientasi ke 0 radian. |
| **Ring 1** *(r = 5.0)* | **Metadata Ring** | Total 24 bit:<br>• 4 bit: Marker length (`len(MARKER)//4 = 4`)<br>• 16 bit: Total byte data (`0 s/d 65535`)<br>• 4 bit: Flags (`bit0: DUP`, `bit1: CRC`, `bit2: ZLIB`) | Memberi tahu decoder berapa panjang data yang harus dibaca, apakah ada salinan kedua, dan apakah datanya dikompresi. |
| **Ring 2+** *(r = 7.0, 9.0, ...)* | **Data Rings** | Tiap cincin berisi:<br>`[16-bit MARKER] + [8-bit Header] + [Payload Chunk] + [1-bit Parity] + [Padding Merah]` | Menyimpan data asli. Marker berfungsi sebagai penanda awal chunk. Header mencatat jumlah byte di cincin tersebut. Parity mengecek keabsahan chunk. |
| **Titik Pusat** *(r = 0.0)* | **Center Dot** | Lingkaran Kuning (`radius = 0.5`) | Membantu identifikasi visual titik pusat koordinat $(0, 0)$. |

---

## ⚙️ 3. BEDAH KODE: `radialEn.py` (ENCODER)

### A. Parameter & Konstanta Inti (Baris 29–38)
* `BASE_R = 3.0` : Jari-jari cincin terdalam (Ring 0 / Anchor).
* `RING_GAP = 2.0` : Jarak antar cincin (radius bertambah 2.0 tiap cincin baru: 3.0, 5.0, 7.0, dst).
* `NODE_R = 0.45` : Jari-jari lingkaran node (diameter = 0.90).
* `MARKER = [1, 1, 1, 0, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0]` : Pola sinkronisasi 16-bit biner unik yang tidak gampang terpicu oleh data acak.
* `MIN_NODE_RADIUS_PX = 6.0` : Batas aman ukuran node di hasil render PNG agar decoder OpenCV tidak buta.

### B. Rumus Kapasitas & Jarak Node (Baris 56 & 140)
```python
bpr = max(M + 8 + 1, int((2 * math.pi * r) / (NODE_R * 2.3)))
```
* **Keliling lingkaran:** $K = 2 \times \pi \times r$.
* **Kenapa dibagi `(NODE_R * 2.3)`?**
  - Diameter node adalah $2 \times 0.45 = 0.90$.
  - `NODE_R * 2.3 = 1.035`.
  - Artinya ada **gap / spasi 15% (0.135 unit)** antar tepi node.
  - *Alasan Teknis:* Kalau tidak ada gap, antialiasing Matplotlib akan membuat warna hijau dan merah berbaur di batas piksel, sehingga OpenCV menganggap dua node menyatu menjadi satu kontur raksasa!

### C. Kanvas Adaptif (`plan_layout`, Baris 41–71)
* Kalau data panjang (misal ratusan byte), cincin makin banyak dan gambar melebar.
* Jika kanvas ukurannya tetap (misal 12 inch terus), resolusi per node akan mengecil sampai di bawah 3 piksel (OpenCV gagal deteksi).
* **Solusi Kamu:** Fungsi `plan_layout()` menghitung jari-jari terjauh (`lim`), lalu otomatis membesarkan ukuran gambar (`fig_inch`) agar radius node di file PNG akhir dijamin selalu $\ge 6\text{ px}$.

### D. Penempatan Sudut Node (`draw_ring`, Baris 73–79)
```python
ang = 2 * math.pi * i / bpr - math.pi / 2
x, y = r * math.cos(ang), r * math.sin(ang)
```
* Dikurangi $\pi/2$ (90 derajat) agar bit index ke-0 selalu berada tepat di **puncak atas (jam 12)**, bukan di jam 3 (sudut 0 standar koordinat polar kartesian).

---

## 🔍 4. BEDAH KODE: `radialD.py` (DECODER)

### A. Pipeline Computer Vision OpenCV (Baris 63–85)
1. **BGR ke HSV (`cv2.cvtColor`):** Memisahkan corak warna (*Hue*) dari kecerahan (*Value*).
2. **Thresholding Warna:**
   - Hijau: `(40, 60, 60)` s/d `(90, 255, 255)`
   - Merah: Menggunakan dua rentang karena warna merah di HSV melintasi batas 0/180:
     `(0, 60, 60)-(10, 255, 255)` **OR** `(160, 60, 60)-(180, 255, 255)`
3. **Kontur & Min Enclosing Circle (`cv2.findContours` & `cv2.minEnclosingCircle`):**
   - Mendapatkan koordinat pusat $(x, y)$ dan radius $r$ untuk setiap bulatan node.
   - Filter `r >= MIN_RADIUS (3px)` untuk membuang bintik *noise*.
4. **Konversi ke Polar:**
   - $dx = x - cx,\; dy = cy - y$
   - $r = \sqrt{dx^2 + dy^2}$ (`math.hypot(dx, dy)`)
   - $\theta = \text{atan2}(dy, dx)$

### B. Dynamic Ring Clustering (Baris 90–103)
* Node diurutkan berdasarkan jaraknya dari pusat ($r$).
* Dikelompokkan ke dalam cincin dengan toleransi adaptif:
  ```python
  ring_tol = max(1.2, 0.6 * med_node_r)
  ```
  *(Jika selisih jarak node berikutnya $\le \text{ring\_tol}$, masukkan ke cincin yang sama; jika lebih, buat cincin baru).*

### C. Kalibrasi Rotasi / Anti-Rotate (Baris 108–116)
* Di `rings[0]`, cari node yang bernilai hijau (`bit == 1`).
* Sudut node hijau ini disimpan sebagai `north_angle`.
* Semua node di seluruh cincin dinormalisasi sudutnya:
  ```python
  n[1] = (n[1] - north_angle + 2 * math.pi) % (2 * math.pi)
  ```
* Setelah itu, tiap cincin di-sort ulang berdasarkan sudut barunya. Hasilnya: gambar yang tadinya miring 45°, 90°, atau terbalik langsung kembali tegak lurus sempurna!

### D. Rekonstruksi Data & Redundansi (Baris 184–218)
* Jika `FLAG_DUP` (bit 0) aktif: data ditulis dua kali (`Copy 1` dan `Copy 2`).
* Jika ada cincin yang cacat/rusak di `Copy 1`, decoder akan melakukan **Per-Byte Stitching**: lubang byte yang hilang di `Copy 1` ditambal menggunakan byte yang selamat dari `Copy 2`.
* Integritas akhir diverifikasi dengan checksum **CRC-32**. Jika CRC valid, data langsung didekompresi via **zlib**.

---

## 🧪 5. SENJATA DEMO LIVE: `_test_e2e.py`
Jika admin minta: *"Coba run test atau buktiin kodenya jalan!"*

Buka terminal dan jalankan:
```powershell
python _test_e2e.py
```
**Hasil:** `17/17 PASS`!
Jelaskan ke admin apa yang dites:
1. `T01-T03`: Encoding & decoding teks biasa, Unicode, dan format v2.
2. `T04`: **Rotasi 90 derajat** (membuktikan kalibrasi jangkar berfungsi).
3. `T05-T06`: **Simulasi kerusakan fisik** (merusak Ring luar pada salinan 1, dan merusak Ring dalam pada salinan 2 — sistem tetap sukses memulihkan 100% data berkat double-copy recovery).
4. `T07-T08`: Deteksi kegagalan (korupsi parah langsung fail secara eksplisit, tidak ada *silent corruption*).
5. `T14-T15`: Proteksi kapasitas 8KB & kanvas adaptif.
6. `T17`: **Zip-Slip Protection** (mencegah eksploitasi path traversal saat ekstraksi zip).

---

## 🎯 6. JAWABAN CEPAT PERTANYAAN JEBAKAN ADMIN

### Q1: "Kenapa gak pakai Reed-Solomon kayak QR Code biasa, kok malah CRC-32 + Double Copy?"
> **Jawaban:** 
> *"QR Code standar pakai Reed-Solomon karena grid kotaknya kontinu dan padat. Di RadialQR versi 2 ini, saya memprioritaskan latensi dan transparansi per-cincin. Dengan double-copy ber-offset dan CRC-32 tail, sistem punya ketahanan terhadap **ring-loss error** (misal 1 cincin utuh buram/terhapus, salinan di cincin lain masih utuh). Di roadmap v3, saya memang merencanakan integrasi Reed-Solomon per blok cincin."*

### Q2: "Kenapa di `radialEn.py` ada `matplotlib.use('Agg')`?"
> **Jawaban:** 
> *"`Agg` adalah backend non-GUI (Anti-Grain Geometry). Wajib dipasang di awal agar Matplotlib bisa me-render gambar ke buffer memori/file di lingkungan server/web tanpa memerlukan layar (X11 / display server) dan mencegah memory leak."*

### Q3: "Kenapa pakai `cv2.minEnclosingCircle` bukan HoughCircles?"
> **Jawaban:** 
> *"`cv2.HoughCircles` sangat lambat dan sangat sensitif terhadap parameter resolusi (`dp`, `param1`, `param2`) ketika ukuran radius lingkaran bervariasi karena zoom. Pendekatan `inRange` + `findContours` + `minEnclosingCircle` jauh lebih deterministik, cepat, dan toleran terhadap perubahan skala gambar."*

### Q4: "Kenapa di `radialD.py` ada `safe_extract_zip()`? Apa bahayanya `zipfile.extractall()`?"
> **Jawaban:** 
> *"`zipfile.extractall()` rentan terhadap celah keamanan **Zip-Slip (Path Traversal)**. Jika seseorang mengunggah file zip dengan nama file berbahaya seperti `../../etc/passwd` atau `../../app.py`, mengekstraknya secara naif bisa menimpa file penting sistem. `safe_extract_zip()` memeriksa `os.path.commonpath` untuk memastikan semua file hanya diekstrak di dalam direktori target."*

---

## 🛠️ 7. CONTOH LIVE MODIFIKASI CEPAT (JIKA DISURUH EDIT LANGSUNG)

* **Suruh ganti warna node 0 dari Merah ke Biru:**
  1. Di `radialEn.py` baris 29: ganti `RED = "#FF0000"` jadi `BLUE = "#0000FF"`. Di fungsi `draw_ring` baris 78 ganti `RED` jadi `BLUE`.
  2. Di `radialD.py` baris 72: ganti mask merah dengan range warna biru HSV:
     `blue = cv2.inRange(hsv, (100, 60, 60), (130, 255, 255))`
* **Suruh ganti toleransi ring:**
  - Buka `radialD.py` baris 92: tinggal ubah faktor pengali `0.6` pada `ring_tol = max(1.2, 0.6 * med_node_r)`.
