# test_zlib_full.ps1 -- uji zlib RadialQR v2 (mode publik + vault)
$ErrorActionPreference = "Continue"
Set-Location "C:\Users\Yanto\OneDrive\Dokumen\cam\radialweb"

Write-Host "=== A. Benchmark kompresi zlib ===" -ForegroundColor Cyan
py -3.14 -c @"
import zlib, os
cases = {
    'AAAA x200': b'A' * 200,
    'teks biasa': b'Hello RadialQR v2! Normal sentence.' * 3,
    'acak': os.urandom(200),
}
for name, data in cases.items():
    packed = zlib.compress(data, 9)
    tag = 'LEBIH KECIL (dipakai)' if len(packed) < len(data) else 'mentah (tak kompres)'
    print(f'  {name:12s}: {len(data):4d} -> {len(packed):4d} byte  ratio={len(packed)/len(data):.2f}  {tag}')
"@

Write-Host ""
Write-Host "=== B. Roundtrip Mode 1 (publik) ===" -ForegroundColor Cyan
py -3.14 -c @"
import radialEn as enc, radialD as dec, os
for label, text in [
    ('AAAA x200', 'A'*200),
    ('teks biasa', 'Halo RadialQR v2!' * 3),
    ('unicode', 'Hai 日本語🚀 ' * 5),
]:
    png = enc.encode_data_to_png_bytes(text.encode('utf-8'))
    open('_zt.png','wb').write(png)
    data, flags, err = dec.decode_data_from_image('_zt.png')
    ok = (err is None and data == text.encode('utf-8'))
    print(f'  {label:12s}: zlib={bool(flags&4)}  {\"OK\" if ok else \"GAGAL \"+str(err)}')
os.remove('_zt.png')
"@

Write-Host ""
Write-Host "=== C. Roundtrip Mode 2 (vault) ===" -ForegroundColor Cyan
py -3.14 -c @"
import radialEn as enc, radialD as dec
import os, shutil
msg = 'AAAA' * 50
key, pay = enc.encode_vault_split({'rahasia.txt': msg}, redundant=True)
res = dec.decode_vault(key, output_dir='_vt', payload_path=pay)
p = os.path.join('_vt', 'rahasia.txt')
ok = os.path.exists(p) and open(p,'rb').read() == msg.encode()
print(f'  vault roundtrip: {\"OK\" if ok else \"GAGAL\"}  ({res.splitlines()[0][:40]})')
for f in (key, pay):
    if os.path.exists(f): os.remove(f)
if os.path.exists('_vt'): shutil.rmtree('_vt')
"@

Write-Host ""
Write-Host "SELESAI." -ForegroundColor Green
