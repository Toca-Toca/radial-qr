#!/usr/bin/env python3
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import math
import sys

# --- CONFIG ---
BG, GREEN, RED, YELLOW = "#000000", "#00FF00", "#FF0000", "#FFFF00"
BASE_R, RING_GAP, NODE_R = 3.0, 2.0, 0.45
MARKER = [1,1,1,0, 1,0,1,1, 0,0,0,1, 0,1,1,0] # 16-bit

def draw_ring(ax, r, bits):
    bpr = len(bits)
    for i, bit in enumerate(bits):
        # Angka -math.pi/2 supaya bit pertama ada di posisi "Jam 12" (Utara)
        ang = 2 * math.pi * i / bpr - math.pi / 2
        x, y = r * math.cos(ang), r * math.sin(ang)
        ax.add_patch(Circle((x, y), NODE_R, facecolor=GREEN if bit else RED, edgecolor="none"))

def encode(text, output="radial_pro.png"):
    data_bits = []
    for b in text.encode("utf-8"):
        data_bits.extend(map(int, format(b, "08b")))
    
    fig, ax = plt.subplots(figsize=(12,12), facecolor=BG)
    ax.set_facecolor(BG); ax.set_aspect("equal"); ax.axis("off")

    # --- RING 0: ANCHOR (Kompas) ---
    # Pakai 4 bit saja agar sangat lega dan mudah dibaca
    anchor = [1, 0, 0, 0] 
    draw_ring(ax, BASE_R, anchor)

    # --- RING 1: METADATA ---
    # Kita pakai 24 bit tetap. Info: Marker Length & Total Bytes
    m_val = len(MARKER) // 4
    total_bytes = len(data_bits) // 8
    
    meta = []
    meta.extend([(m_val >> i) & 1 for i in range(3, -1, -1)]) # 4 bit marker info
    meta.extend([(total_bytes >> i) & 1 for i in range(15, -1, -1)]) # 16 bit len
    while len(meta) < 24: meta.append(0)
    draw_ring(ax, BASE_R + RING_GAP, meta)

    # --- RING 2+: DATA ---
    idx, ring_count = 0, 2
    M = len(MARKER)
    while idx < len(data_bits):
        r = BASE_R + ring_count * RING_GAP
        bpr = max(M + 8 + 1, int((2 * math.pi * r) / (NODE_R * 2.3)))
        
        avail_bits = bpr - M - 8 - 1
        num_bytes = min(avail_bits // 8, math.ceil((len(data_bits) - idx) / 8))
        
        if num_bytes == 0 and idx < len(data_bits): num_bytes = 1
        
        chunk_data = data_bits[idx : idx + num_bytes * 8]
        idx += len(chunk_data)
        
        header = [(num_bytes >> i) & 1 for i in range(7, -1, -1)]
        parity = sum(chunk_data) % 2
        
        full_chunk = MARKER + header + chunk_data + [parity]
        while len(full_chunk) < bpr: full_chunk.append(0)
        
        draw_ring(ax, r, full_chunk)
        ring_count += 1

    # Dekorasi Tengah
    ax.add_patch(Circle((0,0), 0.5, facecolor=YELLOW))
    lim = BASE_R + ring_count * RING_GAP + 2
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
    plt.savefig(output, dpi=300, bbox_inches="tight"); plt.close()
    print(f"✅ QR Pro Created: {output} ({ring_count} rings)")

if __name__ == "__main__":
    text = input("Masukkan teks: ")
    encode(text)