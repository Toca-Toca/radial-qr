#!/usr/bin/env python3
"""
force_decode.py -- Paksa decode scrambled_qr.png lapis demi lapis.
Mengikuti PERSIS alur radialD.py (v2), tapi mendump detail tiap lapisan.
Jalankan:  py -3.14 .\force_decode.py <gambar.png>
"""
import sys
import math
import zlib

import cv2
import numpy as np

MIN_RADIUS = 3
MARKER = [1, 1, 1, 0, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0]
M_VAL = len(MARKER) // 4


def bits_to_bytes(bits):
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        v = 0
        for x in bits[i:i + 8]:
            v = (v << 1) | x
        out.append(v)
    return bytes(out)


def find_marker(bits, patt):
    m = len(patt)
    if m == 0:
        return -1
    for i in range(len(bits) - m + 1):
        if bits[i:i + m] == patt:
            return i
    return -1


def find_marker_rot(bits, patt):
    """PAKSA: cari marker walau 'patah' di titik sambung (coba semua rotasi)."""
    db = list(bits) + list(bits)
    n, m = len(bits), len(patt)
    for i in range(n):
        if db[i:i + m] == patt:
            return i if i < n else i - n
    return -1


def hr(title):
    print("\n" + "=" * 64)
    print("  " + title)
    print("=" * 64)


def detect_rings(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print("  Image could not be read!")
        sys.exit(1)
    h, w, _ = img.shape
    cx, cy = w // 2, h // 2
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, (40, 60, 60), (90, 255, 255))
    red = cv2.inRange(hsv, (0, 60, 60), (10, 255, 255)) | \
        cv2.inRange(hsv, (160, 60, 60), (180, 255, 255))
    mask = green | red
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    nodes, radii = [], []
    for c in contours:
        (x, y), r = cv2.minEnclosingCircle(c)
        if r >= MIN_RADIUS:
            bit = 1 if green[int(y), int(x)] > 0 else 0
            dx, dy = x - cx, cy - y
            nodes.append([math.hypot(dx, dy), math.atan2(dy, dx), bit])
            radii.append(r)
    if not nodes:
        print("  No data nodes detected!")
        sys.exit(1)
    nodes.sort(key=lambda n: n[0])
    med = float(np.median(radii))
    ring_tol = max(1.2, 0.6 * med)
    rings, cur = [], [nodes[0]]
    for n in nodes[1:]:
        if abs(n[0] - cur[-1][0]) <= ring_tol:
            cur.append(n)
        else:
            rings.append(cur)
            cur = [n]
    rings.append(cur)
    return img, (cx, cy), rings, med, ring_tol


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "scrambled_qr.png"
    print("IMAGE:", path)

    img, (cx, cy), rings, med, ring_tol = detect_rings(path)

    hr("LAPIS 0: DETEKSI NODE & RING (logika radialD)")
    print(f"  image size        : {img.shape[1]}x{img.shape[0]}")
    print(f"  median node radius: {med:.2f}")
    print(f"  ring_tol (dynamic): {ring_tol:.2f}")
    print(f"  total rings       : {len(rings)}")
    for i, ring in enumerate(rings):
        r = ring[0][0]
        ng = sum(1 for n in ring if n[2] == 1)
        print(f"    ring {i:>2}: radius~{r:6.1f}  nodes={len(ring):>3}  "
              f"green={ng:>3} red={len(ring)-ng:>3}")

    if len(rings) < 3:
        print("  >> FAIL: < 3 rings, metadata ring tidak terdeteksi")
        return

    hr("LAPIS 1: KALIBRASI ANCHOR (offset utara)")
    greens = [n for n in rings[0] if n[2] == 1]
    print(f"  green nodes di Ring 0 = {len(greens)} (harus tepat 1)")
    if len(greens) != 1:
        print(f"  >> FAIL: anchor ambigu ({len(greens)} green, expected 1)")
        return
    north = greens[0][1]
    print(f"  north_angle = {math.degrees(north):.1f} deg -> normalisasi sudut")
    for ring in rings:
        for n in ring:
            n[1] = (n[1] - north + 2 * math.pi) % (2 * math.pi)
        ring.sort(key=lambda x: x[1])

    hr("LAPIS 2: BACA METADATA (marker + total_bytes + flags)")
    meta_bits = [n[2] for n in rings[1]]
    print(f"  meta_bits: {''.join(map(str, meta_bits))}")
    m_val = 0
    for b in meta_bits[0:4]:
        m_val = (m_val << 1) | b
    print(f"  4 bit pertama -> m_val = {m_val} (butuh {M_VAL})")
    if m_val != M_VAL:
        print(f"  >> FAIL: 'Unsupported marker length {m_val*4} bits'")
        pos = find_marker(meta_bits, MARKER)
        posr = find_marker_rot(meta_bits, MARKER)
        print(f"  [diagnosa] find_marker biasa  -> {pos}")
        print(f"  [diagnosa] find_marker rotasi -> {posr}")
        if posr not in (None, -1, 0):
            print(f"  >> PENYEBAB: metadata ring TIDAK sejajar dgn anchor.")
            print(f"     marker ada di offset {posr}; kalibrasi anchor hanya")
            print(f"     menyelaraskan ke node hijau, tidak mencari marker.")
        return
    target_bytes = 0
    for b in meta_bits[4:20]:
        target_bytes = (target_bytes << 1) | b
    flags = 0
    for b in meta_bits[20:24]:
        flags = (flags << 1) | b
    print(f"  total_bytes = {target_bytes}")
    print(f"  flags       = {flags:04b} "
          f"(DUPLICATE={flags&1}, CRC={1 if flags&2 else 0})")
    if target_bytes <= 0:
        print("  >> FAIL: total bytes = 0")
        return

    hr("LAPIS 3: REASSEMBLE DATA (marker + parity + CRC per ring)")
    ncopies = 2 if (flags & 1) else 1
    copies = [dict() for _ in range(ncopies)]
    copy_sizes = [0] * ncopies
    cur = 0
    for i in range(2, len(rings)):
        bits = [n[2] for n in rings[i]]
        idx = find_marker(bits, MARKER)
        if idx < 0:
            print(f"    ring {i}: marker TIDAK ditemukan -> skip")
            continue
        bits = bits[idx:] + bits[:idx]
        num_bytes = 0
        for b in bits[16:24]:
            num_bytes = (num_bytes << 1) | b
        d_start, d_end = 24, 24 + num_bytes * 8
        if num_bytes <= 0 or d_end >= len(bits):
            print(f"    ring {i}: num_bytes={num_bytes} invalid -> skip")
            continue
        chunk = bits[d_start:d_end]
        parity_ok = (sum(chunk) % 2 == bits[d_end])
        print(f"    ring {i}: marker@{idx} num_bytes={num_bytes} "
              f"parity={'OK' if parity_ok else 'BAD'}")
        if cur < ncopies:
            off = copy_sizes[cur]
            if parity_ok:
                copies[cur][off] = bits_to_bytes(chunk)
            copy_sizes[cur] = off + num_bytes
            if copy_sizes[cur] >= target_bytes:
                cur += 1
        if cur >= ncopies:
            break

    hr("LAPIS 4: VERIFIKASI CRC-32")
    use_crc = bool(flags & 2)
    for ci, cp in enumerate(copies):
        buf = bytearray(target_bytes)
        have = bytearray(target_bytes)
        for off, chunk in cp.items():
            if off + len(chunk) <= target_bytes:
                buf[off:off + len(chunk)] = chunk
                have[off:off + len(chunk)] = b"\x01" * len(chunk)
        got = sum(have)
        printable = "".join(chr(b) if 32 <= b < 127 else "."
                            for b in bytes(buf)[:40])
        print(f"  copy {ci}: {got}/{target_bytes} byte | isi={printable!r}")
        if use_crc and got >= target_bytes:
            calc = zlib.crc32(bytes(buf)[:target_bytes - 4])
            exp = int.from_bytes(bytes(buf)[target_bytes - 4:target_bytes], "big")
            print(f"     CRC calc={calc:08x} expected={exp:08x} -> "
                  f"{'OK' if calc == exp else 'MISMATCH (data acak)'}")

    hr("KESIMPULAN")
    print("  Node tetap LENGKAP; yang hilang adalah KESELARASAN posisi bit.")
    print("  Alamat data = sudut node, jadi pergeseran ring = data mati.")


if __name__ == "__main__":
    main()

