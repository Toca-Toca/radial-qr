<h1 align="center">🌀 Radial QR System</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Matplotlib-Plotting-blueviolet?style=for-the-badge" />
  <img src="https://img.shields.io/badge/OpenCV-Computer_Vision-green?style=for-the-badge&logo=opencv&logoColor=white" />
</p>

<p align="center">
  <b>A Proprietary Circular Visual Data Encoding System</b>
</p>

## 📖 Overview

Radial QR is a custom alternative to standard square QR codes. Instead of a matrix, data is encoded into concentric circular rings of binary nodes (green/red). This makes the code not only visually striking but also mathematically fascinating to decode.

## ✨ Features

- **Concentric Data Layers:** Data is encoded sequentially into growing rings.
- **Dynamic Capacity:** Generates as many rings as necessary to fit the encoded payload.
- **Anchor Alignment:** Uses a central "North" anchor ring for automated computer-vision alignment.
- **Resilient Decoding:** Built-in thresholding and rotational calibration via OpenCV to read skewed or rotated images.

## 📂 Structure

```text
radial-qr/
├── radial_qr/
│   ├── encoder.py       # Data -> Circle coordinates (Matplotlib)
│   └── decoder.py       # Image -> Data (OpenCV)
└── main.py              # CLI Interface
```

## 🚀 Getting Started

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Toca-Toca/radial-qr.git
   cd radial-qr
   ```
2. **Install requirements:**
   ```bash
   pip install matplotlib opencv-python numpy
   ```
3. **Encode a message:**
   ```bash
   python main.py encode "Hello World!" -o custom_qr.png
   ```
4. **Decode an image:**
   ```bash
   python main.py decode custom_qr.png
   ```
