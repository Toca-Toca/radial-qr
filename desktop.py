import webview
import sys
import os
import base64

from app import app 

def get_base_path():
    """
    Fungsi sakti biar Flask tetep bisa nemuin folder 'templates' 
    kalau udah di-compile jadi file .exe sama PyInstaller.
    """
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

app.template_folder = os.path.join(get_base_path(), 'templates')
app.static_folder = os.path.join(get_base_path(), 'static')

class Api:
    def __init__(self):
        self.window = None

    def save_image(self, b64_data, filename="radial_vault.png"):
        """
        Fungsi ini bakal dipanggil sama Javascript dari UI.
        Tugasnya ngebuka dialog "Save As..." native Windows.
        """
        if not self.window:
            return False
        
        # Buka dialog Save As bawaan OS
        result = self.window.create_file_dialog(
            webview.SAVE_DIALOG, 
            directory='', 
            save_filename=filename, 
            file_types=('PNG Images (*.png)', 'All Files (*.*)')
        )
        
        if result:
            save_path = result[0]
            # Bersihin prefix base64 dari Javascript (contoh: "data:image/png;base64,iVBO...")
            if ',' in b64_data:
                b64_data = b64_data.split(',')[1]
            
            # Decode dari base64 balik ke binary PNG asli dan di-save
            img_data = base64.b64decode(b64_data)
            with open(save_path, 'wb') as f:
                f.write(img_data)
            return True
        return False

if __name__ == '__main__':
    # Inisialisasi API bridge
    api = Api()
    
    # Bikin native window Windows
    window = webview.create_window(
        title='Radial Vault - Pro Edition', 
        url=app, 
        width=1200, 
        height=800,
        resizable=True,
        maximized=True,
        text_select=False,
        js_api=api # Pasang API bridge ke dalam webview
    )
    
    # Masukin referensi window ke dalem api biar bisa manggil file dialog
    api.window = window
    
    webview.start(private_mode=False)