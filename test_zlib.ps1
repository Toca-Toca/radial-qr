# test_zlib.ps1 -- uji kompresi zlib RadialQR v2 end-to-end
$ErrorActionPreference = "Continue"
Set-Location "C:\Users\Yanto\OneDrive\Dokumen\cam\radialweb"

Write-Host "=== 1. Cek sintaks ===" -ForegroundColor Cyan
py -3.14 -m py_compile radialEn.py
Write-Host ("  radialEn.py exit = " + $LASTEXITCODE)
py -3.14 -m py_compile radialD.py
Write-Host ("  radialD.py  exit = " + $LASTEXITCODE)

Write-Host ""
Write-Host "=== 2. Benchmark kompresi (AAAA vs acak) ===" -ForegroundColor Cyan
py -3.14 -c @"
import zlib, os
cases = {
    'AAAA x200' : b'A' * 200,
    'teks biasa': b'Hello RadialQR v2! This is a normal sentence.' * 3,
    'acak (random)': os.urandom(200),
}
for name, data in cases.items():
    packed = zlib.compress(data, 9)
    ratio = len(packed) / len(data)
    smaller = '<<< LEBIH KECIL (dipakai)' if len(packed) < len(data) else '(dibiarkan mentah)'
    print(f'  {name:16s}: {len(data):4d} -> {len(packed):4d} byte  ratio={ratio:.2f}  {smaller}')
"@

Write-Host ""
Write-Host "=== 3. Roundtrip end-to-end via PNG (Mode 1 publik) ===" -ForegroundColor Cyan
py -3.14 -c @"
import radialEn as enc, radialD as dec

for label, text in [
    ('AAAA x200', 'A'*200),
    ('teks biasa', 'Halo RadialQR v2, ini uji kompresi zlib! ' * 2),
    ('unicode', 'Hai dunia, 日本語🚀 ' * 5),
]:
    png = enc.encode_data_to_png_bytes(text.encode('utf-8'))
    open('_ztest.png','wb').write(png)
    data, flags, err = dec.decode_data_from_image('_ztest.png')
    ok = (err is None and data == text.encode('utf-8'))
    zflag = (flags & 4) != 0
    print(f'  {label:14s}: zlib_flag={zflag}  {'OK' if ok else 'GAGAL: '+str(err)}')

import os
if os.path.exists('_ztest.png'): os.remove('_ztest.png')
"@

Write-Host ""
Write-Host "SELESAI." -ForegroundColor Green
