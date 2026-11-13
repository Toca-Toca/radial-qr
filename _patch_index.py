# -*- coding: utf-8 -*-
"""Patch satu kali templates/index.html untuk Radial Vault v2 (two-file)."""
p = r"C:\Users\Yanto\OneDrive\Dokumen\cam\radialweb\templates\index.html"
s = open(p, encoding="utf-8", newline="").read()
s = s.replace("\r\n", "\n")
n0 = len(s)

# 1. input file: multiple (kunci PNG + vault.enc bisa dipilih sekaligus)
old = '<input type="file" id="file-input" accept="image/*">'
new = '<input type="file" id="file-input" multiple>'
assert s.count(old) == 1, "anchor input: %d" % s.count(old)
s = s.replace(old, new)

# 2. deklarasi state multi-file
old = 'const fileInput = document.getElementById("file-input");'
new = 'const fileInput = document.getElementById("file-input");\n  let selectedFiles = [];'
assert s.count(old) == 1, "anchor fileInput: %d" % s.count(old)
s = s.replace(old, new)

# 3. handler change/drop -> kirim seluruh FileList
old = 'fileInput.addEventListener("change", e => { if (e.target.files[0]) loadDecodeFile(e.target.files[0]); });'
new = 'fileInput.addEventListener("change", e => { if (e.target.files.length) loadDecodeFile(e.target.files); });'
assert s.count(old) == 1, "anchor change: %d" % s.count(old)
s = s.replace(old, new)
old = 'if (e.dataTransfer.files[0]) loadDecodeFile(e.dataTransfer.files[0]); });'
new = 'if (e.dataTransfer.files.length) loadDecodeFile(e.dataTransfer.files); });'
assert s.count(old) == 1, "anchor drop: %d" % s.count(old)
s = s.replace(old, new)

# 4. loadDecodeFile multi-file
old = '''  function loadDecodeFile(file) {
    selectedFile = file; dropZone.querySelector("strong").textContent = file.name; dropZone.querySelector("p").textContent = `${(file.size/1024).toFixed(1)} KB`; btnDecode.disabled = false;
  }'''
new = '''  function loadDecodeFile(files) {
    selectedFiles = Array.from(files);
    if (!selectedFiles.length) return;
    const names = selectedFiles.map(f => f.name).join(" + ");
    const total = selectedFiles.reduce((a, f) => a + f.size, 0);
    dropZone.querySelector("strong").textContent = names;
    dropZone.querySelector("p").textContent = `${selectedFiles.length} file - ${(total/1024).toFixed(1)} KB`;
    btnDecode.disabled = false;
  }'''
assert s.count(old) == 1, "anchor loadDecodeFile: %d" % s.count(old)
s = s.replace(old, new)

# 5. FormData kirim semua file + guard multi
old = 'fd.append("file", selectedFile);'
new = 'selectedFiles.forEach(f => fd.append("file", f));'
assert s.count(old) == 1, "anchor fd: %d" % s.count(old)
s = s.replace(old, new)
old = 'if (!selectedFile) return;'
assert s.count(old) == 1, "anchor guard: %d" % s.count(old)
s = s.replace(old, 'if (!selectedFiles.length) return;')

# 6. nama file hasil unduhan = ZIP bundle
old = 'await window.pywebview.api.save_image(base64data, "radial_vault.png");'
new = 'await window.pywebview.api.save_image(base64data, "radial_vault_bundle.zip");'
assert s.count(old) == 1, "anchor pywebview: %d" % s.count(old)
s = s.replace(old, new)
old = 'a.download = "radial_vault.png";'
new = 'a.download = "radial_vault_bundle.zip";'
assert s.count(old) == 1, "anchor adownload: %d" % s.count(old)
s = s.replace(old, new)

# 7. toast informatif
old = 'showToast("Vault successfully encrypted and saved!");'
new = 'showToast("Vault v2 tersimpan: radial_key.png + vault.enc (1 ZIP)!");'
assert s.count(old) == 1, "anchor toast: %d" % s.count(old)
s = s.replace(old, new)

open(p, "w", encoding="utf-8", newline="").write(s)
print(f"SELESAI - index.html dipatch ({n0} -> {len(s)} chars)")