# Radial QR — Flask Web App

## Cara Jalankan

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Jalankan Flask
```bash
python app.py
```

### 3. Buka browser
```
http://localhost:5000
```

---

## Fitur
- **Real-time preview** — update otomatis 400ms setelah ketik (debounced)
- **Background transparan** pada preview — tidak ada kotak hitam, tidak kepotong
- **Download PNG** — output asli dari Python, background hitam, dpi 300, tanpa efek glow
- **Decode** — upload gambar radial QR, decode via OpenCV (script Python asli)
- **Tab Encode / Decode** dalam satu halaman

## Struktur File
```
radialweb/
├── app.py              ← Flask backend
├── radialEn.py         ← Script encoder asli kamu
├── radialD.py          ← Script decoder asli kamu
├── requirements.txt
└── templates/
    └── index.html      ← UI
```
