# -*- coding: utf-8 -*-
"""Patch app.py: guard kapasitas geometris via plan_layout (413 + saran pecah)."""
p = r"C:\Users\Yanto\OneDrive\Dokumen\cam\radialweb\app.py"
s = open(p, encoding="utf-8", newline="").read().replace("\r\n", "\n")

old = 'MAX_TEXT_BYTES = 1 * 1024 * 1024'
new = 'MAX_TEXT_BYTES = enc_mod.MAX_BYTES_PER_IMAGE  # ~8 KB — selaras kapasitas geometris'
if old in s:
    s = s.replace(old, new)

old = '''        if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            return jsonify({"error": "Teks terlalu besar (maksimal 1 MB)."}), 413'''
new = '''        # Guard kapasitas geometris: tolak data yang akan membuat node
        # terlalu kecil untuk dibaca decoder (+ saran pecah data).
        try:
            enc_mod.plan_layout(len(text.encode("utf-8")), redundant=True, use_crc=True)
        except ValueError as e:
            return jsonify({"error": str(e)}), 413'''
if old in s:
    s = s.replace(old, new)
else:
    raise SystemExit("ANCHOR app.py 413 tidak ditemukan — cek manual")

open(p, "w", encoding="utf-8", newline="").write(s)
print("app.py: guard kapasitas terpasang")
print("plan_layout dipakai:", "plan_layout" in s)