#!/usr/bin/env python3
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import math
import sys
import io
import zipfile
from cryptography.fernet import Fernet

# =================================================================
# CONFIGURATION CONSTANTS
# Visual color scheme and geometric parameters for ring encoding
# =================================================================
BG, GREEN, RED, YELLOW = "#000000", "#00FF00", "#FF0000", "#FFFF00"
BASE_R, RING_GAP, NODE_R = 3.0, 2.0, 0.45  # Ring radius, gap, node radius
MARKER = [1,1,1,0, 1,0,1,1, 0,0,0,1, 0,1,1,0]  # 16-bit synchronization marker
MAGIC_SIGNATURE = b"==RADIAL_VAULT_PAYLOAD=="  # EOF marker for vault detection

def draw_ring(ax, r, bits):
    """
    Render a single ring of colored nodes representing binary data.
    Each node at radius r encodes one bit: GREEN=1, RED=0.
    Angular positions start from 12 o'clock (North) alignment.
    """
    bpr = len(bits)  # Bits per ring
    for i, bit in enumerate(bits):
        # Position at angle: 0 radians = 12 o'clock (top)
        ang = 2 * math.pi * i / bpr - math.pi / 2
        x, y = r * math.cos(ang), r * math.sin(ang)
        ax.add_patch(Circle((x, y), NODE_R, facecolor=GREEN if bit else RED, edgecolor="none"))

def encode_vault(modular_inputs, output="radial_pro.png"):
    """
    Encode and encrypt data into a Radial Vault image.
    
    Process:
    1. Generate Fernet encryption key (AES-128 with HMAC)
    2. Compress input data into ZIP archive
    3. Encrypt ZIP payload using generated key
    4. Render visual QR rings encoding the encryption key
    5. Inject encrypted payload at end of PNG file (steganography)
    
    Args:
        modular_inputs: Dict mapping filenames to content (str or bytes)
        output: Output PNG filename
    """
    # Step 1: Generate encryption key (Fernet uses AES-128-CBC + HMAC-SHA256)
    key = Fernet.generate_key()
    cipher = Fernet(key)
    key_str = key.decode('utf-8')
    print(f"[*] Encryption Key Generated: {key_str}")

    # Step 2: Create compressed ZIP archive in memory
    memory_zip = io.BytesIO()
    with zipfile.ZipFile(memory_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for filename, content in modular_inputs.items():
            if isinstance(content, str):
                content = content.encode('utf-8')
            zf.writestr(filename, content)
    
    zip_bytes = memory_zip.getvalue()

    # Step 3: Encrypt the compressed ZIP data
    encrypted_payload = cipher.encrypt(zip_bytes)

    # Step 4: Generate visual ring pattern (only the decryption key is encoded)
    data_bits = []
    # Convert key string to binary representation (8-bit per character)
    for b in key_str.encode("utf-8"):
        data_bits.extend(map(int, format(b, "08b")))
    
    fig, ax = plt.subplots(figsize=(12,12), facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_aspect("equal")
    ax.axis("off")

    # RING 0: Orientation Anchor/Compass (binary: 1000)
    # This calibration ring defines North direction
    anchor = [1, 0, 0, 0]
    draw_ring(ax, BASE_R, anchor)

    # RING 1: Metadata (marker length + byte count)
    m_val = len(MARKER) // 4  # Normalize marker length
    total_bytes = len(data_bits) // 8  # Total data bytes
    
    meta = []
    # Encode marker length as 4 bits
    meta.extend([(m_val >> i) & 1 for i in range(3, -1, -1)])
    # Encode total byte count as 16 bits
    meta.extend([(total_bytes >> i) & 1 for i in range(15, -1, -1)])
    # Pad to 24 bits
    while len(meta) < 24: meta.append(0)
    draw_ring(ax, BASE_R + RING_GAP, meta)

    # RINGS 2+: Data encoding with error correction
    idx, ring_count = 0, 2
    M = len(MARKER)
    while idx < len(data_bits):
        r = BASE_R + ring_count * RING_GAP
        # Calculate bits per ring based on circumference
        bpr = max(M + 8 + 1, int((2 * math.pi * r) / (NODE_R * 2.3)))
        
        # Available space for payload (ring capacity - marker - header - parity)
        avail_bits = bpr - M - 8 - 1
        num_bytes = min(avail_bits // 8, math.ceil((len(data_bits) - idx) / 8))
        
        if num_bytes == 0 and idx < len(data_bits): num_bytes = 1
        
        # Extract data chunk
        chunk_data = data_bits[idx : idx + num_bytes * 8]
        idx += len(chunk_data)
        
        # Encode: Marker + Header (byte count) + Payload + Parity check
        header = [(num_bytes >> i) & 1 for i in range(7, -1, -1)]
        parity = sum(chunk_data) % 2  # Even parity for error detection
        
        full_chunk = MARKER + header + chunk_data + [parity]
        # Pad ring to capacity
        while len(full_chunk) < bpr: full_chunk.append(0)
        
        draw_ring(ax, r, full_chunk)
        ring_count += 1

    # Render central bullseye marker and finalize canvas
    ax.add_patch(Circle((0,0), 0.5, facecolor=YELLOW))
    lim = BASE_R + ring_count * RING_GAP + 2
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    
    # Save high-resolution PNG image
    plt.savefig(output, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"✅ Radial Vault image created: {output} ({ring_count} rings)")

    # Step 5: Inject encrypted payload at end of PNG file (steganography)
    # This embedding technique exploits the fact that PNG readers ignore data beyond EOF
    with open(output, 'ab') as f:
        f.write(MAGIC_SIGNATURE)
        f.write(encrypted_payload)
    print(f"✅ Encrypted payload successfully embedded in image file (steganography)")

if __name__ == "__main__":
    # Interactive CLI for encoding data into Radial Vault
    file_name = input("Enter virtual filename (example: secret.txt): ")
    text = input("Enter text content: ")
    
    # Wrap input as dictionary to support modular multi-file encoding
    inputs = {
        file_name: text
    }
    encode_vault(inputs)