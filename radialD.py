#!/usr/bin/env python3
"""
Radial Vault — Decoder
=========================
Hardening from the 2026-08-29 audit:
- DYNAMIC RING_TOL: scaled from the median detected node radius
  (a fixed 1.2 px constant is fragile across dpi/resolution changes).
- Ambiguous anchor -> explicit error (previously: first green node, wrong rotation).
- Unknown marker length -> explicit error (previously: silently aligned garbage).
- Format: dup/CRC-32 flags -> two-copy recovery + CRC verification.
- Format: zlib flag (bit2) -> transparent decompression of the body.
"""
import math
import os
import io
import zipfile
import zlib

import cv2
import numpy as np
from cryptography.fernet import Fernet, InvalidToken

MIN_RADIUS = 3
MAGIC_SIGNATURE = b"==RADIAL_VAULT_PAYLOAD=="
MARKER = [1, 1, 1, 0, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0]
M_VAL = len(MARKER) // 4  # = 4


def bits_to_bytes(bits):
    """list of bits -> bytes (drop trailing bits below 8)."""
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        v = 0
        for x in bits[i:i + 8]:
            v = (v << 1) | x
        out.append(v)
    return bytes(out)


def bits_to_text(bits):
    return bits_to_bytes(bits).decode("utf-8", errors="replace")


def find_marker(bits, marker_patt):
    """Find the marker pattern in a bit stream. Returns index or -1."""
    m = len(marker_patt)
    if m == 0:
        return -1
    for i in range(len(bits) - m + 1):
        if bits[i:i + m] == marker_patt:
            return i
    return -1


def decode_data_from_image(image_path):
    """
    Decode payload bytes from a radial ring image.

    Returns: (data_bytes, flags, error_message)
      - error_message is None on success.
    """
    img = cv2.imread(image_path)
    if img is None:
        return None, 0, "Image could not be read (unknown format?)"

    h, w, _ = img.shape
    cx, cy = w // 2, h // 2
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    green = cv2.inRange(hsv, (40, 60, 60), (90, 255, 255))
    red = cv2.inRange(hsv, (0, 60, 60), (10, 255, 255)) | cv2.inRange(hsv, (160, 60, 60), (180, 255, 255))
    mask = green | red
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    nodes = []
    node_radii = []
    for c in contours:
        (x, y), r = cv2.minEnclosingCircle(c)
        if r >= MIN_RADIUS:
            bit = 1 if green[int(y), int(x)] > 0 else 0
            dx, dy = x - cx, cy - y
            nodes.append([math.hypot(dx, dy), math.atan2(dy, dx), bit])
            node_radii.append(r)

    if not nodes:
        return None, 0, "No data nodes detected"
    nodes.sort(key=lambda n: n[0])

    # --- DYNAMIC ring tolerance (scaled from median node radius) ---
    med_node_r = float(np.median(node_radii))
    ring_tol = max(1.2, 0.6 * med_node_r)

    rings = []
    cur = [nodes[0]]
    for n in nodes[1:]:
        if abs(n[0] - cur[-1][0]) <= ring_tol:
            cur.append(n)
        else:
            rings.append(cur)
            cur = [n]
    rings.append(cur)

    if len(rings) < 3:
        return None, 0, "Incomplete QR: metadata ring not detected"

    # --- Anchor calibration: EXACTLY one green node in the innermost ring ---
    greens = [n for n in rings[0] if n[2] == 1]
    if len(greens) != 1:
        return None, 0, f"Calibration failed: ambiguous anchor ({len(greens)} green nodes, expected 1)"
    north_angle = greens[0][1]

    for ring in rings:
        for n in ring:
            n[1] = (n[1] - north_angle + 2 * math.pi) % (2 * math.pi)
        ring.sort(key=lambda x: x[1])

    # --- Metadata ring ---
    meta_bits = [n[2] for n in rings[1]]
    if len(meta_bits) < 24:
        return None, 0, "Metadata ring corrupted"

    m_val = 0
    for b in meta_bits[0:4]:
        m_val = (m_val << 1) | b
    if m_val != M_VAL:
        return None, 0, f"Unsupported marker length {m_val * 4} bits (only {M_VAL * 4} bits)."

    target_bytes = 0
    for b in meta_bits[4:20]:
        target_bytes = (target_bytes << 1) | b
    flags = 0
    for b in meta_bits[20:24]:
        flags = (flags << 1) | b

    if target_bytes <= 0:
        return None, flags, "Total bytes = 0 (empty payload)"

    # --- Data assembly (two copies + CRC + per-chunk recovery) ---
    expected_copies = 2 if (flags & 1) else 1
    copies = [dict() for _ in range(expected_copies)]   # offset_byte -> chunk bytes
    copy_sizes = [0 for _ in range(expected_copies)]
    cur = 0
    skipped = 0
    for i in range(2, len(rings)):
        bits = [n[2] for n in rings[i]]
        idx = find_marker(bits, MARKER)
        if idx < 0:
            skipped += 1
            continue
        bits = bits[idx:] + bits[:idx]
        header = bits[16:24]
        num_bytes = 0
        for b in header:
            num_bytes = (num_bytes << 1) | b
        d_start = 24
        d_end = d_start + num_bytes * 8
        if num_bytes <= 0 or d_end >= len(bits):
            skipped += 1
            continue
        chunk = bits[d_start:d_end]
        off = copy_sizes[cur]
        parity_ok = (sum(chunk) % 2 == bits[d_end])
        n_left = target_bytes - off
        if cur + 1 < expected_copies and num_bytes > n_left:
            # chunk crosses the copy boundary -> split (legacy format compatibility)
            if parity_ok:
                copies[cur][off] = bits_to_bytes(chunk[:n_left * 8])
                copies[cur + 1][0] = bits_to_bytes(chunk[n_left * 8:])
            copy_sizes[cur] = target_bytes
            copy_sizes[cur + 1] = num_bytes - n_left
            cur += 1
        else:
            if parity_ok:
                copies[cur][off] = bits_to_bytes(chunk)
            else:
                skipped += 1
            copy_sizes[cur] = off + num_bytes
            if copy_sizes[cur] >= target_bytes:
                cur += 1
        if cur >= expected_copies:
            break

    def build_copy(cidx):
        buf = bytearray(target_bytes)
        have = bytearray(target_bytes)
        for off, chunk in copies[cidx].items():
            if off + len(chunk) <= target_bytes:
                buf[off:off + len(chunk)] = chunk
                have[off:off + len(chunk)] = b"\x01" * len(chunk)
        return buf, have

    use_crc = bool(flags & 2)

    def crc_ok(blob):
        return (use_crc and len(blob) >= target_bytes and
                zlib.crc32(blob[:target_bytes - 4]) ==
                int.from_bytes(blob[target_bytes - 4:target_bytes], "big"))

    d1, have1 = build_copy(0)
    data = None
    if all(have1) and (not use_crc or crc_ok(d1)):
        data = bytes(d1)
    elif expected_copies == 2:
        d2, have2 = build_copy(1)
        if all(have2) and (not use_crc or crc_ok(d2)):
            data = bytes(d2)
        else:
            # Per-byte recovery: holes in copy 1 are filled from copy 2
            merged = bytearray(d1)
            have = bytearray(have1)
            for i in range(target_bytes):
                if not have[i] and have2[i]:
                    merged[i] = d2[i]
                    have[i] = 1
            if all(have) and (not use_crc or crc_ok(bytes(merged))):
                data = bytes(merged)

    if data is None:
        missing = have1.count(0)
        return None, flags, (f"Data incomplete/corrupt ({missing}/{target_bytes} bytes missing) — "
                             f"damage exceeds redundancy capacity (bad rings: {skipped})")

    if use_crc:
        data = data[:-4]

    # zlib flag (bit2): data disimpan terkompresi -> kembalikan ke bentuk asli
    if flags & 4:
        try:
            data = zlib.decompress(data)
        except zlib.error:
            return None, flags, "Decompression failed (corrupt zlib payload)."

    return data, flags, None


def decode_visual_qr(image_path):
    """
    Extract text/key from a radial ring image.
    Returns: (text, error) — compatible with older callers.
    """
    data, flags, err = decode_data_from_image(image_path)
    if err:
        return None, err
    return data.decode("utf-8", errors="replace"), None


def safe_extract_zip(zip_bytes, output_dir):
    """
    Extract a ZIP with zip-slip (path traversal) protection.
    Adopted from the prjck version. Returns: list of file names.
    """
    extracted = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.startswith("/") or ".." in name:
                raise ValueError(f"Path traversal detected in ZIP: {name!r}")
        for name in zf.namelist():
            zf.extract(name, output_dir)
            extracted.append(name)
    return extracted


def decode_vault(image_path, output_dir="vault_extracted", payload_path=None):
    """
    Open a vault:
      - two-file : image_path = radial_key.png, payload_path = vault.enc
      - legacy   : payload_path=None, payload embedded in the PNG (with warning)
    """
    if not os.path.exists(image_path):
        return "Error: Image file not found."

    with open(image_path, "rb") as f:
        file_data = f.read()

    if payload_path is not None:
        if not os.path.exists(payload_path):
            return "Error: Payload file (.enc) not found."
        with open(payload_path, "rb") as f:
            encrypted_payload = f.read()
    else:
        sig_idx = file_data.find(MAGIC_SIGNATURE)
        if sig_idx == -1:
            key, err = decode_visual_qr(image_path)
            if err:
                return f"Error: {err}"
            return f"Standard Radial QR (no encryption) — text:\n{key}"
        encrypted_payload = file_data[sig_idx + len(MAGIC_SIGNATURE):]

    key_str, err = decode_visual_qr(image_path)
    if err:
        return f"ERROR: Key scan failed. ({err})"
    if not key_str or len(key_str.strip()) < 44:
        return "ERROR: Extracted key is empty/invalid."

    try:
        cipher = Fernet(key_str.strip().encode("utf-8"))
        decrypted_zip = cipher.decrypt(encrypted_payload)
    except InvalidToken:
        return "FATAL: Decryption failed — wrong key or corrupted payload."
    except Exception:
        return "FATAL: Unexpected decryption error."

    os.makedirs(output_dir, exist_ok=True)
    try:
        extracted = safe_extract_zip(decrypted_zip, output_dir)
    except ValueError as ve:
        return f"FATAL: Unsafe archive — {ve}"
    except zipfile.BadZipFile:
        return "FATAL: Decrypted data is not a valid ZIP."

    result = f"[SUCCESS] Vault opened! Files extracted to '{output_dir}/':\n"
    for name in extracted:
        result += f"     - {name}\n"
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Radial Vault decoder")
    parser.add_argument("image", help="Path radial_key.png / vault legacy")
    parser.add_argument("--payload", help="Path vault.enc (mode two-file)", default=None)
    parser.add_argument("--output", default="vault_extracted")
    args = parser.parse_args()
    print("=" * 50)
    print(decode_vault(args.image, output_dir=args.output, payload_path=args.payload))
    print("=" * 50)