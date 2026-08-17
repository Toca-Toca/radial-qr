<h1 align="center">🌀 Radial QR System</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Matplotlib-Visualization-blueviolet?style=for-the-badge" />
  <img src="https://img.shields.io/badge/OpenCV-Computer_Vision-green?style=for-the-badge&logo=opencv&logoColor=white" />
  <img src="https://img.shields.io/badge/NumPy-Computation-013243?style=for-the-badge&logo=numpy" />
</p>

<p align="center">
  <b>💠 A proprietary circular data encoding system that replaces traditional square QR codes with visually striking concentric ring patterns — fully encodable and decodable via CLI.</b>
</p>

---

## 📖 Overview

Radial QR is a **custom-designed alternative to standard QR codes**. Instead of encoding data into a square grid matrix, data is encoded into **concentric circular rings** of binary nodes (green = 1, red = 0). This creates a visually unique and mathematically elegant encoding that is both human-recognizable and machine-decodable.

The system consists of two core components:
- **Encoder** — Converts any UTF-8 text into a circular QR image using Matplotlib
- **Decoder** — Reads a Radial QR image back into text using OpenCV computer vision

## 🎯 How It Works

### Encoding Architecture

Data is distributed across multiple concentric rings, each serving a specific purpose:

```
          Ring 0 (Innermost): ANCHOR 🧭
          ├─ 4 nodes (1 green + 3 red)
          └─ "North Star" alignment marker

          Ring 1: METADATA 📊
          ├─ 24 fixed-width bits
          ├─ 4 bits: Marker pattern length
          └─ 16 bits: Total data byte count

          Ring 2+: DATA 📦
          ├─ Variable bits per ring (scales with circumference)
          ├─ Each ring: [16-bit Marker] + [8-bit Byte Count] + [Data Bits] + [Padding]
          └─ Rings grow outward until all data is encoded
```

### Bit Encoding
- **Green nodes (🟢)** = Binary `1`
- **Red nodes (🔴)** = Binary `0`
- Text is converted to UTF-8 bytes, then to binary bits
- Each bit becomes a colored circle placed at calculated angular positions using trigonometry

### Decoding Pipeline

```
┌───────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌───────────┐
│ Load      │─►│ HSV Color   │─►│ Contour     │─►│ Ring Group  │─►│ Bit       │
│ Image     │   │ Threshold   │   │ Detection   │   │ Assignment  │   │ Extraction│
└───────────┘   └────────────┘   └────────────┘   └────────────┘   └───────────┘
    │                                                                  │
    │    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐           │
    └─►│ Calibrate   │─►│ Find Marker │─►│ Decode      │◄───────────┘
         │ North (R0)  │   │ Pattern     │   │ UTF-8 Text  │
         └─────────────┘   └─────────────┘   └─────────────┘
```

1. **HSV Thresholding** — Separates green and red nodes using HSV color ranges
2. **Contour Detection** — Finds circular node boundaries using `cv2.findContours`
3. **Ring Grouping** — Clusters nodes by radial distance from center with tolerance
4. **North Calibration** — Uses Ring 0's single green node as rotational reference
5. **Marker Detection** — Locates the 16-bit synchronization pattern in each data ring
6. **Data Extraction** — Reads bits between markers and converts back to UTF-8 text

## ✨ Key Features

- 🎯 **Concentric Data Layers** — Data distributed across growing circular rings
- 📊 **Dynamic Capacity** — Automatically generates as many rings as needed to fit the payload
- 🧭 **Anchor Alignment** — Central "North" ring with a single green node for rotational calibration
- 🔄 **Resilient Decoding** — Handles skewed, rotated, or scaled images via OpenCV contour analysis
- 🎬 **CLI Interface** — Simple encode/decode commands via `argparse`
- 📀 **16-bit Marker Sync** — Each data ring contains a unique bit pattern for reliable data extraction
- 📨 **UTF-8 Support** — Encodes any Unicode text including emojis and special characters

## 📂 Project Structure

```text
radial-qr/
├── .github/workflows/
│   ├── pylint.yml                # Code quality checks
│   └── python-publish.yml        # PyPI publish workflow
├── radial_qr/
│   ├── __init__.py               # Package init
│   ├── encoder.py                # 🎨 Data → Circular QR image (Matplotlib)
│   │                              #    └─ Ring drawing, node placement, trigonometry
│   └── decoder.py                # 🔍 Image → Text (OpenCV)
│                                   #    └─ HSV thresholding, contour analysis, ring grouping
└── main.py                       # 🚀 CLI interface (argparse)
```

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| **Matplotlib** | Generating circular QR images with precise circle patches |
| **OpenCV** | Image processing, HSV thresholding, contour detection |
| **NumPy** | Numerical array operations for image data |
| **argparse** | CLI command parsing (encode/decode subcommands) |

## 🚀 Getting Started

### Prerequisites
- Python 3.8+

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Toca-Toca/radial-qr.git
   cd radial-qr
   ```

2. **Install dependencies:**
   ```bash
   pip install matplotlib opencv-python numpy
   ```

### Usage

**Encode a message:**
```bash
python main.py encode "Hello World!" -o my_radial_code.png
```

**Decode an image:**
```bash
python main.py decode my_radial_code.png
```

**Output example:**
```
========================================
       RADIAL PRO DECODER RESULT
========================================
Hello World!
========================================
```

## 🧮 Mathematical Foundation

Each node's position is calculated using polar-to-Cartesian conversion:

```
x = radius × cos(θ) — where θ = 2π × (index / bits_per_ring) - π/2
y = radius × sin(θ) — offset by -π/2 to start at "12 o'clock" (North)
```

Ring radii grow linearly: `r = BASE_RADIUS + ring_index × RING_GAP`

Bits per ring scale with circumference: `bpr = max(min_bits, 2πr / node_diameter)`

## 📄 License

This project is open source. Feel free to learn from it and build upon it.

---

<p align="center">
  <i>Built with 🐍 Python and ❤️ by <a href="https://github.com/Toca-Toca">Toca-Toca</a></i>
</p>
