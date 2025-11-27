import sys
import os

def resource_path(relative_path):
    """ 取得資源的絕對路徑 (支援 PyInstaller 打包) """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def sanitize_filename(name):
    """ 去除檔名中的非法字元 """
    return "".join([c for c in name if c not in r'\/:*?"<>|']).strip()