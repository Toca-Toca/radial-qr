#!/usr/bin/env python3
import cv2
import numpy as np
import math
import sys
import os
import io
import zipfile
from cryptography.fernet import Fernet

# =================================================================
# CONFIGURATION - Synchronized with Encoder Module
# Detection tolerance and visibility thresholds for ring decoding
# =================================================================
RING_TOL = 1.2  # Radius tolerance for grouping nodes into rings
MIN_RADIUS = 3  # Minimum radius for node detection
MAGIC_SIGNATURE = b"==RADIAL_VAULT_PAYLOAD=="  # Vault format identifier

def bits_to_text(bits):
    """
    Convert a list of binary digits to UTF-8 text.
    Processes 8-bit chunks and decodes with error tolerance.
    """
    out = []
    for i in range(0, len(bits), 8):
        b = bits[i:i+8]
        if len(b) < 8: break
        v = 0
        for x in b: v = (v << 1) | x
        out.append(v)
    return bytes(out).decode("utf-8", errors="replace")

def find_marker(bits, marker_patt):
    """
    Locate synchronization marker pattern in bit sequence.
    Returns first match index or -1 if not found.
    """
    m = len(marker_patt)
    for i in range(len(bits)):
        if bits[i:i+m] == marker_patt:
            return i
    return -1

def decode_visual_qr(image_path):
    """
    Extract encryption key from Radial Vault visual QR rings.
    
    Algorithm:
    1. Load image and convert to HSV color space
    2. Segment GREEN (bit=1) and RED (bit=0) nodes via threshold
    3. Group nodes into concentric rings by radius
    4. Calibrate angular alignment using anchor ring
    5. Decode metadata (ring count, byte count)
    6. Extract data with error checking (parity verification)
    
    Returns: (extracted_text, error_message)
    """
    img = cv2.imread(image_path)
    if img is None: return None, "Image not found"

    h, w, _ = img.shape
    cx, cy = w // 2, h // 2
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Color segmentation using HSV thresholding
    # GREEN: H=60-90°, S=60-255%, V=60-100%
    green = cv2.inRange(hsv, (40, 60, 60), (90, 255, 255))
    # RED: H=0-10° or H=160-180° (wrap-around hue)
    red = cv2.inRange(hsv, (0, 60, 60), (10, 255, 255)) | cv2.inRange(hsv, (160, 60, 60), (180, 255, 255))
    
    # Combine masks and find contours
    mask = green | red
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Extract node positions and values (radius, angle, bit)
    nodes = []
    for c in contours:
        (x, y), r = cv2.minEnclosingCircle(c)
        if r >= MIN_RADIUS:
            bit = 1 if green[int(y), int(x)] > 0 else 0
            dx, dy = x - cx, cy - y
            nodes.append([math.hypot(dx, dy), math.atan2(dy, dx), bit])

    if not nodes: return None, "No data found"
    nodes.sort(key=lambda n: n[0])  # Sort by radius

    # Group nodes into rings by radius proximity
    rings = []
    cur = [nodes[0]]
    for n in nodes[1:]:
        if abs(n[0] - cur[-1][0]) <= RING_TOL:
            cur.append(n)
        else:
            rings.append(cur)
            cur = [n]
    rings.append(cur)

    if len(rings) < 3: return None, "Incomplete QR: Metadata missing"

    # Angular calibration using anchor ring (RING 0)
    # Find the GREEN node (bit=1) which marks North orientation
    r0_nodes = rings[0]
    north_node = None
    for n in r0_nodes:
        if n[2] == 1:
            north_node = n
            break
    
    if not north_node: return None, "Orientation failed: Anchor not found"
    north_angle = north_node[1]

    # Normalize all angles relative to anchor
    for r_idx in range(len(rings)):
        for n_idx in range(len(rings[r_idx])):
            cur_ang = rings[r_idx][n_idx][1]
            new_ang = (cur_ang - north_angle + 2*math.pi) % (2*math.pi)
            rings[r_idx][n_idx][1] = new_ang
        rings[r_idx].sort(key=lambda x: x[1])  # Sort by angle

    # Decode metadata from RING 1 (marker length + total bytes)
    meta_bits = [n[2] for n in rings[1]]
    if len(meta_bits) < 20: return None, "Metadata ring corrupted"
    
    # Extract marker length (4 bits) and convert
    m_val = 0
    for b in meta_bits[0:4]: m_val = (m_val << 1) | b
    DYNAMIC_M_LEN = m_val * 4
    
    # Extract byte count (16 bits)
    target_bytes = 0
    for b in meta_bits[4:20]: target_bytes = (target_bytes << 1) | b
    
    # Construct expected marker pattern based on metadata
    DYNAMIC_MARKER = [1,1,1,0, 1,0,1,1, 0,0,0,1, 0,1,1,0] if DYNAMIC_M_LEN == 16 else []

    # Decode data from RING 2 onwards with error verification
    all_data_bits = []
    for i in range(2, len(rings)):
        bits = [n[2] for n in rings[i]]
        # Find synchronization marker to align bit stream
        idx = find_marker(bits, DYNAMIC_MARKER)
        
        if idx < 0: continue  # No marker found, skip ring

        # Rotate bits to align marker at position 0
        bits = bits[idx:] + bits[:idx]
        
        # Extract header (byte count for this ring)
        header = bits[DYNAMIC_M_LEN : DYNAMIC_M_LEN + 8]
        num_bytes = 0
        for b in header: num_bytes = (num_bytes << 1) | b
        
        # Extract payload and verify parity
        d_start = DYNAMIC_M_LEN + 8
        d_end = d_start + (num_bytes * 8)
        
        if d_end < len(bits):
            chunk = bits[d_start:d_end]
            parity = bits[d_end]
            # Accept only if parity check passes
            if sum(chunk) % 2 == parity:
                all_data_bits.extend(chunk)
        
        # Stop when sufficient data extracted
        if len(all_data_bits) // 8 >= target_bytes:
            break

    return bits_to_text(all_data_bits[:target_bytes * 8]), None

def decode_vault(image_path, output_dir="vault_extracted"):
    """
    Fully decrypt and extract data from a Radial Vault image.
    
    Process:
    1. Load image file and detect vault signature
    2. Extract encryption key from visual QR rings
    3. Extract encrypted payload from file EOF
    4. Decrypt ZIP archive using Fernet (AES-128)
    5. Extract and save files locally
    
    Args:
        image_path: Path to vault PNG file
        output_dir: Directory to extract files into
    
    Returns: Status/result message
    """
    if not os.path.exists(image_path):
        return "Error: Image file not found."

    # Read file and search for magic signature indicating vault format
    with open(image_path, 'rb') as f:
        file_data = f.read()
    
    signature_index = file_data.find(MAGIC_SIGNATURE)
    if signature_index == -1:
        # Backward compatibility: treat as standard Radial QR (no encryption)
        key, err = decode_visual_qr(image_path)
        if err: return err
        return f"Standard Radial QR (no encryption) - Extracted text:\n{key}"
    
    # Extract encrypted payload from end of file (steganographic embedding)
    encrypted_payload = file_data[signature_index + len(MAGIC_SIGNATURE):]

    # Scan visual rings to extract encryption key
    extracted_key_str, err = decode_visual_qr(image_path)
    
    if err:
        return f"ERROR: QR scan failed or image corrupted. ({err})"
    if not extracted_key_str:
        return "ERROR: Extracted encryption key is empty."

    # Decrypt payload using extracted key (Fernet uses AES-128-CBC + HMAC)
    try:
        cipher = Fernet(extracted_key_str.encode('utf-8'))
        decrypted_zip_bytes = cipher.decrypt(encrypted_payload)
    except Exception as e:
        return f"FATAL: Decryption failed (wrong key or corrupted payload). Access denied. ({e})"

    # Extract modular data to local directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    memory_zip = io.BytesIO(decrypted_zip_bytes)
    extracted_files = []
    try:
        with zipfile.ZipFile(memory_zip, 'r') as zf:
            zf.extractall(output_dir)
            extracted_files = zf.namelist()
    except zipfile.BadZipFile:
        return "FATAL: Decrypted data is not a valid ZIP archive."

    result_text = f"[SUCCESS] Vault opened! Files extracted to '{output_dir}/':\n"
    for name in extracted_files:
        result_text += f"     ├── {name}\n"
    return result_text

if __name__ == "__main__":
    # Command-line interface for decoding Radial Vault images
    import argparse
    parser = argparse.ArgumentParser(description="Decode Radial Vault encrypted images")
    parser.add_argument("image", help="Path to vault image file")
    args = parser.parse_args()
    
    # Display banner and decode
    print("\n" + "="*50)
    print("     RADIAL VAULT - DECRYPTION UTILITY")
    print("="*50)
    print(decode_vault(args.image))
    print("="*50)