#!/usr/bin/env python3
"""Radial Vault — Encoder (hardened).

Two-file design: the key (PNG) is kept SEPARATE from the payload (.enc).
Format metadata: [4-bit marker][16-bit length][4-bit flags], where
flag bit0 = payload written twice (redundancy), bit1 = CRC-32 tail,
bit2 = payload is zlib-compressed (auto; only if it shrinks).
Adaptive canvas keeps node radius >= MIN_NODE_RADIUS_PX for long data."""
import math
import io
import os
import sys
import zipfile
import zlib
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from cryptography.fernet import Fernet

BG, GREEN, RED, YELLOW = "#000000", "#00FF00", "#FF0000", "#FFFF00"
BASE_R, RING_GAP, NODE_R = 3.0, 2.0, 0.45
MARKER = [1, 1, 1, 0, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0]
MAGIC_SIGNATURE = b"==RADIAL_VAULT_PAYLOAD=="  # legacy vault only
FLAG_DUP, FLAG_CRC = 1, 2
FLAG_ZLIB = 4              # payload stored zlib-compressed (only if it shrinks)
ZLEVEL = 9                 # zlib compression level (max)
MIN_NODE_RADIUS_PX = 6.0   # decoder needs radius >= 3px; keep 2x margin
BASE_FIG_INCH, BASE_DPI = 12.0, 300
MAX_BYTES_PER_IMAGE = 8 * 1024  # practical render limit; larger -> split data


def plan_layout(num_bytes, redundant=True, use_crc=True, dpi=BASE_DPI):
    """Simulate ring packing without rendering: capacity guard + adaptive
    canvas size (node radius guaranteed >= MIN_NODE_RADIUS_PX).
    Raises ValueError when num_bytes > MAX_BYTES_PER_IMAGE."""
    if num_bytes > MAX_BYTES_PER_IMAGE:
        raise ValueError(
            f"Data of {num_bytes} bytes exceeds one radial image capacity "
            f"(max {MAX_BYTES_PER_IMAGE // 1024} KB). Split the data into parts.")
    payload_len = num_bytes + (4 if use_crc else 0)
    copies = 2 if redundant else 1

    def _pack(bits_len):
        idx, ring_count, M = 0, 2, len(MARKER)
        while idx < bits_len:
            r = BASE_R + ring_count * RING_GAP
            bpr = max(M + 8 + 1, int((2 * math.pi * r) / (NODE_R * 2.3)))
            avail = bpr - M - 8 - 1
            num = min(avail // 8, (bits_len - idx) // 8)
            if num == 0:
                num = 1
            idx += num * 8
            ring_count += 1
        return ring_count

    total_rings = _pack(payload_len * 8) * copies
    lim = BASE_R + total_rings * RING_GAP + 2
    fig_inch = max(BASE_FIG_INCH, 2.0 * MIN_NODE_RADIUS_PX * lim / (NODE_R * dpi))
    node_r_px = NODE_R * (fig_inch * dpi / 2.0) / lim
    return {"total_rings": total_rings, "lim": lim, "fig_inch": fig_inch,
            "node_radius_px": node_r_px, "canvas_px": int(fig_inch * dpi)}


def draw_ring(ax, r, bits):
    bpr = len(bits)
    for i, bit in enumerate(bits):
        ang = 2 * math.pi * i / bpr - math.pi / 2
        x, y = r * math.cos(ang), r * math.sin(ang)
        ax.add_patch(Circle((x, y), NODE_R, facecolor=GREEN if bit else RED, edgecolor="none"))


def bits_from_bytes(data):
    return [int(b) for byte in data for b in format(byte, "08b")]


def crc32_bytes(data):
    return zlib.crc32(data).to_bytes(4, "big")


def maybe_compress(data):
    """Return (stored_bytes, compressed_flag). Compresses with zlib only when
    the result is actually smaller; otherwise stores the data untouched."""
    packed = zlib.compress(data, ZLEVEL)
    if len(packed) < len(data):
        return packed, FLAG_ZLIB
    return data, 0


def timestamp_name(prefix, ext):
    """Build a file name stamped with the current date and time,
    e.g. prefix-10-04-2026_17-42-05.ext (month-day-year_hour-minute-second)."""
    stamp = datetime.now().strftime("%m-%d-%Y_%H-%M-%S")
    return f"{prefix}-{stamp}{ext}"


def encode_data_to_png_bytes(data, transparent=False, dpi=BASE_DPI, redundant=True, use_crc=True):
    """Render data (bytes) -> PNG radial ring, format. The adaptive canvas
    grows with the data so nodes never shrink below a readable size.
    The body is zlib-compressed automatically when that makes it smaller
    (flag bit2); the CRC-32 is always computed on the ORIGINAL data."""
    data = bytes(data)
    stored, zflag = maybe_compress(data)
    payload = stored + (crc32_bytes(stored) if use_crc else b"")
    total_bytes = len(payload)
    flags = ((FLAG_DUP if redundant else 0) | (FLAG_CRC if use_crc else 0) | zflag)
    stream = bits_from_bytes(payload)

    plan = plan_layout(len(payload) + (0 if use_crc else 0), redundant, use_crc, dpi)
    fig_inch = plan["fig_inch"]

    fig, ax = plt.subplots(figsize=(fig_inch, fig_inch), facecolor="none" if transparent else BG)
    ax.set_facecolor("none" if transparent else BG)
    ax.set_aspect("equal")
    ax.axis("off")

    draw_ring(ax, BASE_R, [1, 0, 0, 0])  # RING 0: anchor (one green node = north)

    meta = [(len(MARKER) // 4 >> i) & 1 for i in range(3, -1, -1)]
    meta += [(total_bytes >> i) & 1 for i in range(15, -1, -1)]
    meta += [(flags >> i) & 1 for i in range(3, -1, -1)]
    draw_ring(ax, BASE_R + RING_GAP, meta)  # RING 1: metadata

    # RING 2+: each copy is chunked separately so no chunk ever crosses
    # the boundary between copy 1 and copy 2.
    stream_copies = [stream] if not redundant else [stream, stream]
    ring_count, M = 2, len(MARKER)
    for stream_part in stream_copies:
        idx = 0
        while idx < len(stream_part):
            r = BASE_R + ring_count * RING_GAP
            bpr = max(M + 8 + 1, int((2 * math.pi * r) / (NODE_R * 2.3)))
            avail = bpr - M - 8 - 1
            num_bytes = min(avail // 8, (len(stream_part) - idx) // 8)
            if num_bytes == 0 and idx < len(stream_part):
                num_bytes = 1
            chunk = stream_part[idx: idx + num_bytes * 8]
            idx += len(chunk)
            header = [(num_bytes >> i) & 1 for i in range(7, -1, -1)]
            parity = sum(chunk) % 2
            full = MARKER + header + chunk + [parity]
            while len(full) < bpr:
                full.append(0)
            draw_ring(ax, r, full)
            ring_count += 1

    ax.add_patch(Circle((0, 0), 0.5, facecolor=YELLOW))
    lim = BASE_R + ring_count * RING_GAP + 2
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def encode_vault_split(modular_inputs, key_out=None, payload_out=None, redundant=True):
    """TWO-FILE VAULT: the key (PNG) is separate from the payload (.enc).
    Output names default to a timestamped form, e.g. radial_key-10-04-2026_17-42-05.png
    and vault-10-04-2026_17-42-05.enc."""
    if key_out is None:
        key_out = timestamp_name("key", ".png")
    if payload_out is None:
        payload_out = timestamp_name("vault", ".enc")
    key = Fernet.generate_key()
    cipher = Fernet(key)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name, content in modular_inputs.items():
            safe = os.path.basename(name) or "data.txt"
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(safe, content)
    payload = cipher.encrypt(buf.getvalue())
    with open(payload_out, "wb") as f:
        f.write(payload)
    png = encode_data_to_png_bytes(key, redundant=redundant)
    with open(key_out, "wb") as f:
        f.write(png)
    print(f"Key    : {key_out}  (DO NOT share)")
    print(f"Payload: {payload_out}  (safe to share)")
    return key_out, payload_out


def encode_legacy_single(modular_inputs, output=None):
    """LEGACY FORMAT (INSECURE) - key + payload in a single file.
    Kept for backward compatibility only."""
    if output is None:
        output = timestamp_name("vault", ".png")
    key = Fernet.generate_key()
    cipher = Fernet(key)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name, content in modular_inputs.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(name, content)
    payload = cipher.encrypt(buf.getvalue())
    png = encode_data_to_png_bytes(key, redundant=False, use_crc=False)
    with open(output, "wb") as f:
        f.write(png)
        f.write(MAGIC_SIGNATURE)
        f.write(payload)
    print(f"LEGACY VAULT created: {output} (old format - INSECURE)")
    return output


if __name__ == "__main__":
    print("1. Public mode")
    print("2. Vault mode")
    mode = input("Choose mode [1/2]: ").strip()
    if mode == "1":
        text = input("Text: ")
        png = encode_data_to_png_bytes(text.encode("utf-8"))
        out = timestamp_name("public", ".png")
        with open(out, "wb") as f:
            f.write(png)
        print(f"Image created: {out} (safe to share)")
    else:
        file_name = input("Virtual file name (e.g. secret.txt): ")
        text = input("Text: ")
        encode_vault_split({file_name: text})
