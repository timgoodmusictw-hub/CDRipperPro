import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import time
import os
from PIL import Image, ImageTk
from config import DEFAULT_OUTPUT_DIR, DISCID_DLL
from engine import AudioRipperEngine
from metadata import MetadataManager

class CandidateSelectionDialog(tk.Toplevel):
    """ [新增] 搜尋結果選擇視窗 """
    def __init__(self, parent, candidates):
        super().__init__(parent)
        self.title("選擇專輯資訊版本")
        self.geometry("600x400")
        self.candidates = candidates
        self.selected_data = None
        self.setup_ui()
        self.transient(parent); self.grab_set()

    def setup_ui(self):
        ttk.Label(self, text="找到多筆資料，請選擇最符合的一個：", padding=10).pack(fill="x")
        
        # 建立 Treeview 表格
        columns = ("source", "artist", "album", "year", "tracks")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        
        self.tree.heading("source", text="來源")
        self.tree.heading("artist", text="演出者")
        self.tree.heading("album", text="專輯名稱")
        self.tree.heading("year", text="年份")
        self.tree.heading("tracks", text="軌數")
        
        self.tree.column("source", width=120)
        self.tree.column("artist", width=120)
        self.tree.column("album", width=180)
        self.tree.column("year", width=60)
        self.tree.column("tracks", width=50)
        
        # 插入資料
        for i, c in enumerate(self.candidates):
            self.tree.insert("", "end", iid=str(i), values=(
                c.get("source", "Unknown"),
                c.get("artist", ""),
                c.get("album", ""),
                c.get("year", ""),
                len(c.get("tracks", []))
            ))
            
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)
        self.tree.bind("<Double-1>", self.on_confirm) # 雙擊選擇

        # 按鈕
        frame_btn = ttk.Frame(self, padding=10)
        frame_btn.pack(fill="x")
        ttk.Button(frame_btn, text="選擇此版本", command=self.on_confirm).pack(side="right", padx=5)
        ttk.Button(frame_btn, text="取消 / 使用空白模板", command=self.destroy).pack(side="right", padx=5)

    def on_confirm(self, event=None):
        sel = self.tree.selection()
        if not sel: return
        idx = int(sel[0])
        self.selected_data = self.candidates[idx]
        self.destroy()

class TrackEditorDialog(tk.Toplevel):
    """ 專輯資訊編輯視窗 """
    def __init__(self, parent, metadata):
        super().__init__(parent)
        self.title("編輯專輯資訊")
        self.geometry("800x600")
        self.result_data = None
        self.metadata = metadata
        self.setup_ui()
        self.transient(parent); self.grab_set()

    def setup_ui(self):
        frame_top = ttk.LabelFrame(self, text="專輯資訊 (全域)", padding=10)
        frame_top.pack(fill="x", padx=10, pady=5)
        
        self.vars = {}
        fields = [("專輯演出者 (Album Artist)", "artist"), ("專輯名稱 (Album)", "album"), ("年份 (Year)", "year"), ("流派 (Genre)", "genre")]
        for i, (label, key) in enumerate(fields):
            ttk.Label(frame_top, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=2)
            val = self.metadata.get(key, "Unknown")
            var = tk.StringVar(value=val)
            ttk.Entry(frame_top, textvariable=var, width=50).grid(row=i, column=1, sticky="w", padx=5, pady=2)
            self.vars[key] = var

        frame_list = ttk.LabelFrame(self, text="曲目列表", padding=5)
        frame_list.pack(fill="both", expand=True, padx=10, pady=5)

        header_frame = ttk.Frame(frame_list)
        header_frame.pack(side="top", fill="x", padx=0, pady=2)
        ttk.Label(header_frame, text="#", width=4, anchor="center").grid(row=0, column=0, padx=5, sticky="w")
        ttk.Label(header_frame, text="曲目名稱 (Title)", width=38, anchor="w").grid(row=0, column=1, padx=5, sticky="w")
        ttk.Label(header_frame, text="個別演出者 (Artist)", width=28, anchor="w").grid(row=0, column=2, padx=5, sticky="w")

        canvas = tk.Canvas(frame_list)
        scrollbar = ttk.Scrollbar(frame_list, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def _on_mousewheel(event): canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.track_vars = []
        for i, track in enumerate(self.metadata["tracks"]):
            row = i
            ttk.Label(self.scrollable_frame, text=track['num'], width=4, anchor="center").grid(row=row, column=0, padx=5, pady=2)
            t_title = tk.StringVar(value=track['title'])
            ttk.Entry(self.scrollable_frame, textvariable=t_title, width=40).grid(row=row, column=1, padx=5, pady=2)
            t_artist = tk.StringVar(value=track.get('artist', self.metadata.get('artist', '')))
            ttk.Entry(self.scrollable_frame, textvariable=t_artist, width=30).grid(row=row, column=2, padx=5, pady=2)
            self.track_vars.append((t_title, t_artist))

        frame_btn = ttk.Frame(self, padding=10)
        frame_btn.pack(fill="x")
        ttk.Button(frame_btn, text="儲存變更", command=self.on_save).pack(side="right", padx=5)
        ttk.Button(frame_btn, text="取消", command=self.destroy).pack(side="right", padx=5)

    def on_save(self):
        new_meta = self.metadata.copy()
        new_meta["artist"] = self.vars["artist"].get()
        new_meta["album"] = self.vars["album"].get()
        new_meta["year"] = self.vars["year"].get()
        new_meta["genre"] = self.vars["genre"].get()
        new_tracks = []
        for i, (v_title, v_artist) in enumerate(self.track_vars):
            updated_track = self.metadata["tracks"][i].copy()
            updated_track["title"] = v_title.get()
            updated_track["artist"] = v_artist.get()
            new_tracks.append(updated_track)
        new_meta["tracks"] = new_tracks
        self.result_data = new_meta
        self.destroy()

class RipperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Python CD Ripper Pro v2.7 (Selector)")
        self.root.geometry("750x700")
        
        self.engine = AudioRipperEngine(self.log_message)
        self.meta_mgr = MetadataManager(self.log_message)
        self.current_metadata = None
        self.cover_image_ref = None

        missing = self.engine.check_tools()
        if not self.meta_mgr.check_dependency(): missing.append(DISCID_DLL)
        if missing: messagebox.showerror("缺少元件", f"請檢查 tools 資料夾:\n{missing}")
            
        self.setup_ui()
        self.refresh_drives()

    def setup_ui(self):
        frame_settings = ttk.LabelFrame(self.root, text="設定", padding=10)
        frame_settings.pack(fill="x", padx=10, pady=5)

        ttk.Label(frame_settings, text="光碟機:").grid(row=0, column=0, sticky="w")
        self.combo_drives = ttk.Combobox(frame_settings, state="readonly", width=8); self.combo_drives.grid(row=0, column=1, padx=5)
        ttk.Button(frame_settings, text="重整", command=self.refresh_drives).grid(row=0, column=2)

        ttk.Label(frame_settings, text="格式:").grid(row=0, column=3, sticky="e", padx=10)
        self.combo_format = ttk.Combobox(frame_settings, state="readonly", width=8, values=["m4a", "flac", "mp3"]); self.combo_format.current(0); self.combo_format.grid(row=0, column=4)

        self.var_use_cdtext = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame_settings, text="包含本機 CD-Text", variable=self.var_use_cdtext).grid(row=1, column=0, columnspan=3, sticky="w", pady=5)

        ttk.Label(frame_settings, text="輸出目錄:").grid(row=2, column=0, sticky="w")
        self.var_output = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        ttk.Entry(frame_settings, textvariable=self.var_output, width=45).grid(row=2, column=1, columnspan=3, sticky="w", padx=5)
        ttk.Button(frame_settings, text="瀏覽...", command=self.browse_folder).grid(row=2, column=4)

        frame_mid = ttk.Frame(self.root)
        frame_mid.pack(fill="x", padx=10, pady=5)

        frame_info = ttk.LabelFrame(frame_mid, text="專輯資訊", padding=10)
        frame_info.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.lbl_album_info = ttk.Label(frame_info, text="請先搜尋資訊...", font=("Microsoft JhengHei", 10, "bold"), wraplength=400)
        self.lbl_album_info.pack(anchor="w", pady=10)

        frame_cover = ttk.LabelFrame(frame_mid, text="封面預覽", padding=5)
        frame_cover.pack(side="right", padx=(5, 0))
        self.lbl_cover = ttk.Label(frame_cover, text="無圖片", width=15, anchor="center")
        self.lbl_cover.pack(pady=5)
        self.btn_cover = ttk.Button(frame_cover, text="選擇封面...", command=self.on_select_cover, state="disabled")
        self.btn_cover.pack(fill="x")

        frame_actions = ttk.Frame(self.root, padding=10)
        frame_actions.pack(fill="x", padx=10)
        self.btn_read = ttk.Button(frame_actions, text="1. 搜尋資訊", command=self.on_read_cd); self.btn_read.pack(side="left", padx=5)
        self.btn_edit = ttk.Button(frame_actions, text="2. 編輯資訊", command=self.on_edit_meta, state="disabled"); self.btn_edit.pack(side="left", padx=5)
        self.btn_start = ttk.Button(frame_actions, text="3. 開始轉檔", command=self.on_start_rip, state="disabled"); self.btn_start.pack(side="left", padx=5)
        self.btn_stop = ttk.Button(frame_actions, text="停止", command=self.on_stop, state="disabled"); self.btn_stop.pack(side="right", padx=5)

        lbl_credit = ttk.Label(self.root, text="Created by tim_good_music", font=("Arial", 8), foreground="gray"); lbl_credit.pack(side="bottom", pady=2)
        self.lbl_status = ttk.Label(self.root, text="就緒", relief="sunken", anchor="w"); self.lbl_status.pack(fill="x", side="bottom")
        self.txt_log = scrolledtext.ScrolledText(self.root, height=10, state="disabled", font=("Consolas", 9)); self.txt_log.pack(fill="both", expand=True, padx=10, pady=5)

    def log_message(self, msg): self.root.after(0, self._append_log, msg)
    def _append_log(self, msg):
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.txt_log.see("end"); self.txt_log.config(state="disabled")
        self.lbl_status.config(text=msg)

    def refresh_drives(self):
        drives = self.meta_mgr.get_cd_drives()
        self.combo_drives['values'] = drives
        if drives: self.combo_drives.current(0)

    def browse_folder(self):
        if d := filedialog.askdirectory(): self.var_output.set(d)

    def update_cover_preview(self, img_path):
        try:
            if img_path and os.path.exists(img_path):
                pil_img = Image.open(img_path)
                pil_img.thumbnail((120, 120))
                tk_img = ImageTk.PhotoImage(pil_img)
                self.lbl_cover.config(image=tk_img, text="")
                self.cover_image_ref = tk_img
            else:
                self.lbl_cover.config(image="", text="無圖片")
        except:
            self.lbl_cover.config(image="", text="錯誤")

    def on_select_cover(self):
        file_path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg;*.jpeg;*.png")])
        if file_path:
            if self.current_metadata:
                self.current_metadata["cover_path"] = file_path
                self.update_cover_preview(file_path)
                self.log_message(f"已手動設定封面: {os.path.basename(file_path)}")

    def on_read_cd(self):
        drive = self.combo_drives.get()
        if not drive: return
        self.btn_edit.config(state="disabled"); self.btn_start.config(state="disabled"); self.btn_cover.config(state="disabled")
        
        def task():
            self.log_message(f"讀取 {drive} (搜尋所有來源)...")
            
            # [修正] 呼叫 fetch_all_candidates 而不是 fetch
            candidates = self.meta_mgr.fetch_all_candidates(drive, self.var_use_cdtext.get())
            
            # 必須回到主執行緒操作 GUI
            self.root.after(0, lambda: self.handle_search_results(candidates))

        threading.Thread(target=task, daemon=True).start()

    def handle_search_results(self, candidates):
        meta = None
        
        if not candidates:
            # 沒找到資料 -> 空白模板
            meta = {
                "source": "Manual",
                "artist": "Unknown Artist", "album": "Unknown Album", "year": time.strftime("%Y"), "genre": "Pop", "cover_path": None,
                "tracks": [{"num": str(i+1), "title": f"Track {i+1:02d}", "artist": "Unknown Artist"} for i in range(15)]
            }
            self.log_message("⚠️ 未找到資料，使用空白模板")
        else:
            # [修正] 彈出選擇視窗
            dialog = CandidateSelectionDialog(self.root, candidates)
            self.root.wait_window(dialog)
            if dialog.selected_data:
                meta = dialog.selected_data
                self.log_message(f"✅ 已選擇來源: {meta.get('source')}")
            else:
                # 使用者取消 -> 空白模板
                meta = {
                    "source": "Manual",
                    "artist": "Unknown Artist", "album": "Unknown Album", "year": time.strftime("%Y"), "genre": "Pop", "cover_path": None,
                    "tracks": [{"num": str(i+1), "title": f"Track {i+1:02d}", "artist": "Unknown Artist"} for i in range(15)]
                }
                self.log_message("⚠️ 使用者取消選擇，使用空白模板")

        self.current_metadata = meta
        info_str = f"{meta['artist']} - {meta['album']} [{meta.get('genre','')}]\n{len(meta['tracks'])} Tracks"
        self.update_ui_after_read(info_str, meta.get("cover_path"))

    def update_ui_after_read(self, info_text, cover_path):
        self.lbl_album_info.config(text=info_text, foreground="blue")
        self.update_cover_preview(cover_path)
        self.btn_edit.config(state="normal"); self.btn_start.config(state="normal"); self.btn_cover.config(state="normal")

    def on_edit_meta(self):
        if not self.current_metadata: return
        editor = TrackEditorDialog(self.root, self.current_metadata)
        self.root.wait_window(editor)
        
        if editor.result_data:
            self.current_metadata = editor.result_data
            info_str = f"{self.current_metadata['artist']} - {self.current_metadata['album']} [{self.current_metadata.get('genre','')}]\n{len(self.current_metadata['tracks'])} Tracks"
            self.lbl_album_info.config(text=info_str + " (已修改)", foreground="green")
            self.update_cover_preview(self.current_metadata.get("cover_path"))
            self.log_message("✅ 資訊已更新")

    def on_start_rip(self):
        drive = self.combo_drives.get(); out = self.var_output.get(); fmt = self.combo_format.get()
        self.btn_start.config(state="disabled"); self.btn_read.config(state="disabled"); self.btn_edit.config(state="disabled"); self.btn_cover.config(state="disabled")
        self.btn_stop.config(state="normal")
        def task():
            try: self.engine.start_rip(drive, out, fmt, self.current_metadata)
            finally: self.root.after(0, self.reset_ui)
        threading.Thread(target=task, daemon=True).start()

    def on_stop(self): self.engine.stop_flag = True
    def reset_ui(self):
        self.btn_read.config(state="normal"); self.btn_start.config(state="normal"); self.btn_edit.config(state="normal"); self.btn_cover.config(state="normal")
        self.btn_stop.config(state="disabled"); self.log_message("--- 結束 ---")