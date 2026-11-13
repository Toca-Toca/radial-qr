#!/usr/bin/env python3
"""
Radial Vault v2 — Flask backend (hardened, hasil audit 2026-08-29)
==================================================================
- TWO-FILE VAULT: /api/download kini mengembalikan ZIP berisi
  radial_key.png (kunci) + vault.enc (payload) + BACA_SAYA.txt.
  Kunci TIDAK lagi ditempel di file yang sama dengan payload
  (kelemahan kritirs desain lama: satu PNG = kunci + isi sekaligus).
- /api/decode menerima:
    (a) dua file sekaligus: kunci PNG + vault.enc
    (b) bundle ZIP dari /api/download (di-upload balik)
    (c) vault legacy satu-file (diproses + peringatan keamanan)
    (d) radial QR biasa tanpa enkripsi
- Batas upload 10 MB; validasi magic PNG; pesan error generik ke klien.
- debug=False default (set env RADIAL_DEBUG=1 untuk pengembangan).
"""
import io
import os
import tempfile
import zipfile

from flask import Flask, render_template, request, jsonify, send_file
from cryptography.fernet import Fernet, InvalidToken

import radialEn as enc_mod
import radialD as dec_mod

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB (Flask -> 413 otomatis)

MAGIC = enc_mod.MAGIC_SIGNATURE
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_TEXT_BYTES = enc_mod.MAX_BYTES_PER_IMAGE  # ~32 KB — selaras kapasitas geometris
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

BUNDLE_README = (
    "RADIAL VAULT v2 (TWO-FILE)\n"
    "==========================\n"
    "1. radial_key.png : GAMBAR KUNCI - jangan dibagikan ke siapa pun.\n"
    "2. vault.enc      : payload terenkripsi (boleh dibagikan/disimpan).\n"
    "3. Untuk membuka: upload KEDUA file sekaligus di tab Decode.\n"
    "Keamanan data = kepemilikan radial_key.png. Simpan seperti kunci fisik.\n"
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/encode", methods=["POST"])
def api_encode():
    # Preview ditangani frontend (canvas). Endpoint dipertahankan demi kompatibilitas.
    return jsonify({"status": "ok", "note": "preview client-side; unduh via /api/download"})


def _fernet_zip(text):
    """Buat kunci Fernet + enkripsi teks sebagai ZIP terkompresi."""
    key = Fernet.generate_key()
    cipher = Fernet(key)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("dataPack.txt", text.encode("utf-8"))
    return key, cipher.encrypt(buf.getvalue())


@app.route("/api/download", methods=["POST"])
def api_download():
    """TWO-FILE VAULT: kembalikan ZIP (radial_key.png + vault.enc + panduan)."""
    try:
        body = request.get_json(silent=True) or {}
        text = str(body.get("text", ""))
        if not text.strip():
            return jsonify({"error": "Teks kosong."}), 400
        # Guard kapasitas geometris: tolak data yang akan membuat node
        # terlalu kecil untuk dibaca decoder (+ saran pecah data).
        try:
            enc_mod.plan_layout(len(text.encode("utf-8")), redundant=True, use_crc=True)
        except ValueError as e:
            return jsonify({"error": str(e)}), 413

        key, encrypted_payload = _fernet_zip(text)
        key_png = enc_mod.encode_data_to_png_bytes(key, redundant=True, use_crc=True)

        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("radial_key.png", key_png)
            zf.writestr("vault.enc", encrypted_payload)
            zf.writestr("BACA_SAYA.txt", BUNDLE_README)
        zbuf.seek(0)
        return send_file(zbuf, mimetype="application/zip", as_attachment=True,
                         download_name="radial_vault_bundle.zip")
    except Exception:
        app.logger.exception("Gagal membuat vault")
        return jsonify({"error": "Gagal memproses vault di server."}), 500


def _save_temp(data, suffix):
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


def _decode_key_from_png(png_data):
    """Validasi PNG + ekstrak kunci dari gambar cincin. Returns (key_str, err)."""
    if not bytes(png_data[:8]) == PNG_MAGIC:
        return None, "File kunci bukan PNG valid."
    path = _save_temp(png_data, ".png")
    try:
        return dec_mod.decode_visual_qr(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _open_vault(key_str, encrypted_payload):
    """Dekripsi payload dengan kunci. Returns (result_text, err)."""
    key_str = (key_str or "").strip()
    if len(key_str) != 44:
        return None, "Kunci hasil decode tidak valid (bukan kunci Fernet)."
    try:
        cipher = Fernet(key_str.encode("utf-8"))
        decrypted = cipher.decrypt(encrypted_payload)
    except InvalidToken:
        return None, "Kunci tidak cocok dengan payload (atau payload rusak)."
    except Exception:
        app.logger.exception("dekripsi gagal")
        return None, "Kesalahan dekripsi di server."
    try:
        with zipfile.ZipFile(io.BytesIO(decrypted)) as zf:
            names = zf.namelist()
            if not names:
                return None, "ZIP di dalam payload kosong."
            content = zf.read(names[0]).decode("utf-8", errors="replace")
            return f"--- DEKRIPSI BERHASIL ---\nFile: {names[0]}\n\n{content}", None
    except zipfile.BadZipFile:
        return None, "Payload terdekripsi bukan ZIP valid."


@app.route("/api/decode", methods=["POST"])
def api_decode():
    try:
        uploads = [f for f in request.files.getlist("file") if f and f.filename]
        if not uploads:
            return jsonify({"error": "Tidak ada file diupload."}), 400

        blobs = {}
        for f in uploads:
            data = f.read()
            if len(data) > MAX_UPLOAD_BYTES:
                return jsonify({"error": f"File '{f.filename}' melebihi batas 10 MB."}), 413
            blobs[f.filename] = data

        # --- A) TWO-FILE: kunci PNG + payload (.enc) ---
        if len(blobs) >= 2:
            key_name = next((n for n, d in blobs.items() if bytes(d[:8]) == PNG_MAGIC), None)
            if not key_name:
                return jsonify({"error": "File kunci (.png) tidak ditemukan / bukan PNG valid."}), 400
            payload_name = next(n for n in blobs if n != key_name)
            key_str, err = _decode_key_from_png(blobs[key_name])
            if err:
                return jsonify({"error": f"Scan kunci gagal: {err}"}), 400
            result, err = _open_vault(key_str, blobs[payload_name])
            if err:
                return jsonify({"error": err}), 400
            return jsonify({"result": result + "\n\n(two-file vault: kunci & payload terpisah)"})

        # --- B) SATU FILE ---
        name = next(iter(blobs))
        data = blobs[name]

        # B1: bundle ZIP dari /api/download di-upload balik
        if data[:2] == b"PK" or name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    key_png = zf.read("radial_key.png")
                    payload = zf.read("vault.enc")
            except (KeyError, zipfile.BadZipFile):
                return jsonify({"error": "ZIP tidak berisi radial_key.png + vault.enc."}), 400
            key_str, err = _decode_key_from_png(key_png)
            if err:
                return jsonify({"error": f"Scan kunci gagal: {err}"}), 400
            result, err = _open_vault(key_str, payload)
            if err:
                return jsonify({"error": err}), 400
            return jsonify({"result": result + "\n\n(bundle ZIP two-file)"})

        # validasi PNG untuk jalur berbasis gambar
        if not bytes(data[:8]) == PNG_MAGIC:
            return jsonify({"error": "File bukan PNG valid (butuh kunci PNG / vault legacy / bundle ZIP)."}), 400

        # B2: vault LEGACY satu-file (kunci & payload tertanam) + peringatan
        if data.find(MAGIC) != -1:
            key_str, err = _decode_key_from_png(data)
            if err:
                return jsonify({"error": f"Scan kunci gagal: {err}"}), 400
            encrypted_payload = data[data.find(MAGIC) + len(MAGIC):]
            result, err = _open_vault(key_str, encrypted_payload)
            if err:
                return jsonify({"error": err}), 400
            return jsonify({"result": ("⚠️ FORMAT LEGACY — kunci & payload dulunya satu file "
                                       "(TIDAK AMAN). Segera migrasi ke format two-file.\n\n" + result)})

        # B3: radial QR biasa (tanpa enkripsi)
        key_text, err = _decode_key_from_png(data)
        if err:
            return jsonify({"error": f"Decode gagal: {err}"}), 400
        return jsonify({"result": f"Standard Radial QR (tanpa enkripsi):\n{key_text}"})
    except Exception:
        app.logger.exception("decode gagal")
        return jsonify({"error": "Gagal memproses di server."}), 500


if __name__ == "__main__":
    app.run(debug=os.environ.get("RADIAL_DEBUG") == "1", port=5000)