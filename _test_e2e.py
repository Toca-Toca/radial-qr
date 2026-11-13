# -*- coding: utf-8 -*-
"""E2E security tests — Radial Vault v2 (jalankan dari folder radialweb)."""
import io
import os
import sys
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.chdir(BASE)

import radialEn as enc
import radialD as dec
import cv2
import numpy as np
from app import app

results = []
def check(name, cond, extra=""):
    results.append(cond)
    print(("PASS" if cond else "FAIL"), "-", name, ("| " + str(extra)[:200] if (extra and not cond) else ""))

MSG = "Halo Radial v2! ünïcode 🚀"

# T1 roundtrip v2 (dup + CRC, unicode)
png = enc.encode_data_to_png_bytes(MSG.encode("utf-8"), redundant=True, use_crc=True)
open("_t1.png", "wb").write(png)
data, flags, err = dec.decode_data_from_image("_t1.png")
check("T1 roundtrip v2 (dup+CRC, unicode)", err is None and data == MSG.encode("utf-8") and (flags & 3) == 3, (err, flags))

# T2 rotasi 90 derajat (kalibrasi anchor)
img = cv2.imread("_t1.png")
cv2.imwrite("_t1_rot.png", cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE))
data, flags, err = dec.decode_data_from_image("_t1_rot.png")
check("T2 rotasi 90° tetap terbaca", err is None and data == MSG.encode("utf-8"), err)

# T3 redundansi: ring luar dirusak (annulus multi-threshold) -> copy1 selamat
big = ("A" * 400).encode("utf-8")
open("_t3.png", "wb").write(enc.encode_data_to_png_bytes(big, redundant=True, use_crc=True))
img3 = cv2.imread("_t3.png")
h, w = img3.shape[:2]
Y, X = np.ogrid[:h, :w]
dist2 = (X - w / 2.0) ** 2 + (Y - h / 2.0) ** 2
recovered = None
last_err = None
for f in (0.85, 0.90, 0.95):
    img3d = img3.copy()
    img3d[dist2 > (f * min(h, w) / 2.0) ** 2] = 0
    cv2.imwrite("_t3_dmg.png", img3d)
    data, flags, err = dec.decode_data_from_image("_t3_dmg.png")
    if err is None and data == big:
        recovered = f
        break
    last_err = (f, err)
check("T3 ring luar rusak -> copy1 menyelamatkan data", recovered is not None, last_err)

# T3b: salinan 1 (ring dalam) dirusak -> copy2 menyelamatkan
img3b = cv2.imread("_t3.png")
band = (dist2 > (0.30 * min(h, w) / 2.0) ** 2) & (dist2 < (0.50 * min(h, w) / 2.0) ** 2)
img3b[band] = 0
cv2.imwrite("_t3b.png", img3b)
data, flags, err = dec.decode_data_from_image("_t3b.png")
check("T3b ring dalam rusak -> recovery atau gagal keras (tanpa korupsi senyap)",
      (err is None and data == big) or (err is not None and data is None), (err, str(data)[:40]))

# T4 format v1 legacy tetap terbaca
open("_t4.png", "wb").write(enc.encode_data_to_png_bytes(b"legacy v1 data", redundant=False, use_crc=False))
data, flags, err = dec.decode_data_from_image("_t4.png")
check("T4 format v1 tetap terbaca", err is None and data == b"legacy v1 data" and flags == 0, (err, flags))

# T5 kerusakan parah -> gagal KERAS (tidak ada data senyap)
img5 = cv2.imread("_t1.png")
img5[:, : img5.shape[1] // 2] = 0
cv2.imwrite("_t5.png", img5)
data, flags, err = dec.decode_data_from_image("_t5.png")
check("T5 kerusakan parah -> gagal KERAS", err is not None, (err, str(data)[:40]))

client = app.test_client()

# T6 /api/download -> ZIP bundle 3 file
r = client.post("/api/download", json={"text": "rahasia vault 123"})
ok = r.status_code == 200 and r.mimetype == "application/zip"
zf = zipfile.ZipFile(io.BytesIO(r.data)) if ok else None
check("T6 /api/download -> ZIP 3 file", ok and sorted(zf.namelist()) == ["BACA_SAYA.txt", "radial_key.png", "vault.enc"], (r.status_code, r.mimetype))

# T7 decode dua-file via HTTP
r2 = client.post("/api/decode", data={"file": [
    (io.BytesIO(zf.read("radial_key.png")), "radial_key.png"),
    (io.BytesIO(zf.read("vault.enc")), "vault.enc"),
]})
check("T7 decode two-file via HTTP", r2.status_code == 200 and "rahasia vault 123" in r2.get_json().get("result", ""), r2.get_json())

# T8 decode bundle ZIP langsung
r3 = client.post("/api/decode", data={"file": (io.BytesIO(r.data), "bundle.zip")})
check("T8 decode bundle ZIP via HTTP", r3.status_code == 200 and "rahasia vault 123" in r3.get_json().get("result", ""), r3.get_json())

# T9 legacy satu-file -> dekripsi + peringatan
legacy_path = enc.encode_legacy_single({"s.txt": "pesan legacy lama"})
r4 = client.post("/api/decode", data={"file": (open(legacy_path, "rb"), "legacy.png")})
d4 = r4.get_json()
check("T9 legacy -> dekripsi + peringatan", r4.status_code == 200 and "pesan legacy lama" in d4.get("result", "") and "LEGACY" in d4.get("result", ""), d4)

# T10 teks oversize -> 413
r5 = client.post("/api/download", json={"text": "A" * (1024 * 1024 + 10)})
check("T10 teks > 1MB -> 413", r5.status_code == 413, r5.status_code)

# T11 debug mati default
check("T11 debug=False default", app.debug is False, app.debug)

# T12 tiga file sampah -> 400
r6 = client.post("/api/decode", data={"file": [
    (io.BytesIO(b"1"), "a.txt"), (io.BytesIO(b"2"), "b.txt"), (io.BytesIO(b"3"), "c.txt")]})
check("T12 3 file non-PNG -> 400", r6.status_code == 400, r6.status_code)

# T13 payload rusak dengan kunci benar -> 400 pesan jelas
r7 = client.post("/api/decode", data={"file": [
    (io.BytesIO(zf.read("radial_key.png")), "radial_key.png"),
    (io.BytesIO(b"garbage-payload-bukan-fernet" * 10), "vault.enc"),
]})
check("T13 payload rusak + kunci -> 400", r7.status_code == 400, (r7.status_code, r7.get_json()))

# T14 kapasitas: teks jauh di atas batas geometris -> 413 + saran pecah data
r8 = client.post("/api/download", json={"text": "B" * 100_000})
check("T14 data > kapasitas -> 413 + saran pecah", r8.status_code == 413 and "ecah" in r8.get_json().get("error", ""), (r8.status_code, r8.get_json()))

# T15 roundtrip 4KB (kanvas adaptif: node dijamin >= 6px radius)
big2 = ("A" * 4096).encode("utf-8")
png_big = enc.encode_data_to_png_bytes(big2, redundant=True, use_crc=True)
open("_t15.png", "wb").write(png_big)
data15, flags15, err15 = dec.decode_data_from_image("_t15.png")
check("T15 roundtrip 4KB (canvas adaptif)", err15 is None and data15 == big2, (err15, flags15))

# T16 plan_layout menolak data melebihi MAX_BYTES_PER_IMAGE
try:
    enc.plan_layout(64 * 1024)
    raised = False
except ValueError:
    raised = True
check("T16 plan_layout menolak 64KB", raised)

print()
print("HASIL: %d/%d PASS" % (sum(results), len(results)))