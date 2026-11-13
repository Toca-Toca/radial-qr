#!/usr/bin/env python3
import cv2
import numpy as np
import math
import sys

# =========================
# CONFIG SINKRON DENGAN ENCODER
# =========================
RING_TOL = 1.2
MIN_RADIUS = 3

def bits_to_text(bits):
    out = []
    for i in range(0, len(bits), 8):
        b = bits[i:i+8]
        if len(b) < 8: break
        v = 0
        for x in b: v = (v << 1) | x
        out.append(v)
    return bytes(out).decode("utf-8", errors="replace")

def find_marker(bits, marker_patt):
    m = len(marker_patt)
    for i in range(len(bits)):
        if bits[i:i+m] == marker_patt:
            return i
    return -1

def decode(image_path):
    img = cv2.imread(image_path)
    if img is None: return "Image not found"

    h, w, _ = img.shape
    cx, cy = w // 2, h // 2
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Thresholding Warna
    green = cv2.inRange(hsv, (40, 60, 60), (90, 255, 255))
    red = cv2.inRange(hsv, (0, 60, 60), (10, 255, 255)) | cv2.inRange(hsv, (160, 60, 60), (180, 255, 255))
    
    mask = green | red
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    nodes = []
    for c in contours:
        (x, y), r = cv2.minEnclosingCircle(c)
        if r >= MIN_RADIUS:
            bit = 1 if green[int(y), int(x)] > 0 else 0
            dx, dy = x - cx, cy - y
            # Simpan: [Radius, Sudut, Bit]
            nodes.append([math.hypot(dx, dy), math.atan2(dy, dx), bit])

    if not nodes: return "No data found"
    nodes.sort(key=lambda n: n[0])

    # --- PENGELOMPOKAN RING ---
    rings = []
    cur = [nodes[0]]
    for n in nodes[1:]:
        if abs(n[0] - cur[-1][0]) <= RING_TOL:
            cur.append(n)
        else:
            rings.append(cur); cur = [n]
    rings.append(cur)

    if len(rings) < 3: return "Incomplete QR: Metadata missing"

    # --- STEP 1: KALIBRASI ARAH (RING 0) ---
    # Cari bit 1 (Hijau) di ring paling dalam sebagai penanda UTARA
    r0_nodes = rings[0]
    north_node = None
    for n in r0_nodes:
        if n[2] == 1:
            north_node = n
            break
    
    if not north_node: return "Orientation failed: Anchor not found"
    north_angle = north_node[1]

    # Putar semua sudut relatif terhadap North
    for r_idx in range(len(rings)):
        for n_idx in range(len(rings[r_idx])):
            # Normalisasi sudut agar 0 derajat adalah arah Utara (Jam 12)
            cur_ang = rings[r_idx][n_idx][1]
            new_ang = (cur_ang - north_angle + 2*math.pi) % (2*math.pi)
            rings[r_idx][n_idx][1] = new_ang
        
        # Sortir ulang setiap ring berdasarkan sudut yang sudah dikalibrasi
        rings[r_idx].sort(key=lambda x: x[1])

    # --- STEP 2: BACA METADATA (RING 1) ---
    meta_bits = [n[2] for n in rings[1]]
    if len(meta_bits) < 20: return "Metadata ring corrupted"
    
    # Ambil Marker Length (4 bit awal)
    m_val = 0
    for b in meta_bits[0:4]: m_val = (m_val << 1) | b
    DYNAMIC_M_LEN = m_val * 4
    
    # Ambil Total Bytes (16 bit selanjutnya)
    target_bytes = 0
    for b in meta_bits[4:20]: target_bytes = (target_bytes << 1) | b
    
    print(f"📡 Metadata Detected | Marker: {DYNAMIC_M_LEN} bit | Target: {target_bytes} bytes")

    # --- STEP 3: BACA DATA (RING 2+) ---
    # Kita buat pola marker dinamis berdasarkan info metadata
    # (Di sini kita pakai EB16 sebagai default jika m_val=4)
    # Untuk test ini kita asumsikan pola EB16 jika m_val == 4
    DYNAMIC_MARKER = [1,1,1,0, 1,0,1,1, 0,0,0,1, 0,1,1,0] if DYNAMIC_M_LEN == 16 else []

    all_data_bits = []
    for i in range(2, len(rings)):
        bits = [n[2] for n in rings[i]]
        idx = find_marker(bits, DYNAMIC_MARKER)
        
        if idx < 0: continue # Skip ring tanpa marker valid

        # Align ring
        bits = bits[idx:] + bits[:idx]
        
        # Header Panjang (8 bit)
        header = bits[DYNAMIC_M_LEN : DYNAMIC_M_LEN + 8]
        num_bytes = 0
        for b in header: num_bytes = (num_bytes << 1) | b
        
        # Ekstrak Data
        d_start = DYNAMIC_M_LEN + 8
        d_end = d_start + (num_bytes * 8)
        
        if d_end < len(bits):
            chunk = bits[d_start:d_end]
            parity = bits[d_end]
            if sum(chunk) % 2 == parity:
                all_data_bits.extend(chunk)
        
        # Berhenti jika sudah mencapai target_bytes
        if len(all_data_bits) // 8 >= target_bytes:
            break

    return bits_to_text(all_data_bits[:target_bytes * 8])

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    args = parser.parse_args()
    print("\n" + "="*40)
    print("       RADIAL PRO DECODER RESULT       ")
    print("="*40)
    print(decode(args.image))
    print("="*40)