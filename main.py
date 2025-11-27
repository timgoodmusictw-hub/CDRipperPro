"""
打包指令：
pyinstaller --noconsole --onefile --name="CDRipperPro" --add-data "tools;tools" main.py
"""

import tkinter as tk
from tkinter import ttk
from ui import RipperGUI

if __name__ == "__main__":
    root = tk.Tk()
    # 設定風格讓介面好看一點
    style = ttk.Style()
    try:
        style.theme_use('vista') # Windows 原生風格
    except:
        style.theme_use('clam')
        
    app = RipperGUI(root)
    root.mainloop()