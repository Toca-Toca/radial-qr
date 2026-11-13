# Catatan Perbaikan — Radial Vault v2 (2026-08-29)

Berdasarkan audit keamanan + analisis skalabilitas (skill `security-pen-testing`).

## Kelemahan yang Diperbaiki

### 🔴 Kritis
1. **Single-file vault** — kunci & payload dalam satu PNG = obfuscasi, bukan
   enkripsi. **Fix**: two-file design (`radial_key.png` + `vault.enc`).
   `/api/download` kini mengembalikan ZIP berisi keduanya + panduan.

### 🟠 Tinggi
2. **Redundansi palsu** — `stream_copies` lama memotong stream jadi dua bagian
   (bukan menduplikasi) → tiap bit hanya ada sekali. **Fix**: `[stream, stream]`
   (duplikasi penuh) + tiap salinan di-chunk terpisah (tidak ada chunk yang
   menyeberangi batas salinan — bug tertangkap E2E test).
3. **Korupsi senyap** — parity 1-bit tidak bisa koreksi. **Fix**: CRC-32 tail
   (flags bit1) + recovery per-byte antar salinan + failure selalu LOUD.
4. **`debug=True`** — Werkzeug debugger = RCE saat terekspos. **Fix**:
   `debug=False` default (env `RADIAL_DEBUG=1` untuk dev).

### 🟡 Sedang
5. **Skala data (node mengecil)** — kanvas 12in konstan: node radius menyusut
   seiring data; di bawah 3px decoder buta. **Fix**: `plan_layout()` — simulasi
   packing + **kanvas adaptif** (node dijamin >= 6px radius = 2x ambang decoder)
   + `MAX_BYTES_PER_IMAGE = 8KB` + guard 413 di `/api/download` dengan saran
   pecah data. Terverifikasi: roundtrip 4KB pada kanvas adaptif (T15).
6. **Decoder rapuh** — RING_TOL absolut -> dinamis (median radius node);
   anchor ambigu -> error jelas; marker tak dikenal -> error jelas;
   zip-slip protection (diadopsi dari prjck); pesan error generik ke klien.

## Hasil Verifikasi: 17/17 PASS
Roundtrip v2/CRC/unicode, rotasi 90°, recovery ring luar (copy1), recovery
ring dalam (copy2), format v1 legacy, gagal-keras tanpa korupsi senyap,
ZIP bundle, decode two-file & bundle via HTTP, legacy + peringatan, 413
kapasitas (2x), debug off, 400 multi-file, 400 payload rusak.

## Kapasitas & Data Panjang
- Satu gambar: maks **8 KB** data (node dijamin >= 6px radius via kanvas adaptif).
- Data lebih besar: **pecah menjadi beberapa gambar** (guard 413 memberi tahu).
- Rekomendasi lanjutan: multi-part otomatis (part i/n) + Hamming/RS per chunk.

## Struktur
```
radialweb/
├── app.py            ← Flask v2 (two-file, hardening)
├── radialEn.py       ← encoder v2 (HMAC-ready, kapasitas, adaptif)
├── radialD.py        ← decoder v2 (dinamis, recovery, zip-slip safe)
├── legacy_v1/        ← versi lama (arsip)
├── _test_e2e.py      ← 17 tes regresi
└── dist/RadialVaultGUI.exe  ← PERLU REBUILD (masih format lama!)
```
