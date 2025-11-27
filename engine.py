import os
import subprocess
import time
import ctypes
from mutagen.flac import FLAC, Picture
from mutagen.mp3 import EasyMP3
from mutagen.id3 import ID3, APIC, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover
from utils import resource_path, sanitize_filename
from config import FORMAT_SETTINGS, FREAC_EXE, FFMPEG_EXE

# 擴充 EasyMP3 支援
try:
    EasyMP3.RegisterTextKey('albumartist', 'TPE2')
    EasyMP3.RegisterTextKey('genre', 'TCON')
except: pass

class AudioRipperEngine:
    def __init__(self, logger_func):
        self.log = logger_func
        self.freac_path = resource_path(os.path.join("tools", FREAC_EXE))
        self.ffmpeg_path = resource_path(os.path.join("tools", FFMPEG_EXE))
        self.stop_flag = False

    def check_tools(self):
        missing = []
        if not os.path.exists(self.freac_path): missing.append(FREAC_EXE)
        if not os.path.exists(self.ffmpeg_path): missing.append(FFMPEG_EXE)
        return missing

    def start_rip(self, drive, output_root, target_fmt, metadata=None):
        self.stop_flag = False
        fmt_cfg = FORMAT_SETTINGS.get(target_fmt, FORMAT_SETTINGS["m4a"])

        if not metadata:
            metadata = {
                "artist": "Unknown Artist", "album": f"Rip_{int(time.time())}", "year": time.strftime("%Y"), "genre": "Unknown", "cover_path": None,
                "tracks": [{"num": str(i+1), "title": f"Track {i+1:02d}", "artist": "Unknown Artist"} for i in range(99)]
            }

        # 資料夾路徑
        save_path = os.path.join(output_root, target_fmt, sanitize_filename(metadata['artist']), sanitize_filename(metadata['album']))
        if not os.path.exists(save_path): os.makedirs(save_path)
        self.log(f"📂 輸出位置: {save_path}")

        # 檢查封面檔案是否存在
        cover_ready = False
        if metadata.get("cover_path") and os.path.exists(metadata["cover_path"]):
            cover_ready = True
            self.log(f"  🖼️ 準備嵌入封面: {os.path.basename(metadata['cover_path'])}")

        total = len(metadata['tracks'])
        for track in metadata['tracks']:
            if self.stop_flag: break
            t_num = int(track['num'])
            t_title = track['title']
            
            cda = os.path.join(drive, f"Track{t_num:02d}.cda")
            if not os.path.exists(cda):
                if t_num > 1: break
                else: return

            fname = f"{t_num:02d}. {sanitize_filename(t_title)}.{target_fmt}"
            out_file = os.path.join(save_path, fname)
            wav_temp = os.path.abspath(os.path.join(os.getcwd(), f"temp_{t_num}.wav"))

            self.log(f"💿 [{t_num}/{total}] 處理: {t_title}")
            try:
                # 1. 抓軌 (Rip)
                if os.path.exists(wav_temp): os.remove(wav_temp)
                subprocess.run([self.freac_path, "-d", drive, "-t", str(t_num), "-o", wav_temp],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                
                if not os.path.exists(wav_temp): 
                    self.log(f"  ❌ 抓軌失敗"); continue

                # 2. 轉檔 (Convert) - 確保移除舊的 metadata
                cmd = [self.ffmpeg_path, "-y", "-i", wav_temp, "-c:a", fmt_cfg["codec"]] + fmt_cfg["extra_args"] + ["-vn", "-map_metadata", "-1", out_file]
                subprocess.run(cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

                # 3. 寫入標籤與封面 (Tagging)
                if os.path.exists(out_file):
                    self.write_tags(out_file, metadata, track, target_fmt)
                    self.log(f"  ✅ 完成")
            except Exception as e:
                self.log(f"  ❌ 錯誤: {e}")
            finally:
                if os.path.exists(wav_temp): os.remove(wav_temp)

        if not self.stop_flag:
            self.log("🎉 全部完成！"); self.eject_tray(drive)

    def write_tags(self, filepath, meta, track, fmt):
        """ 寫入標籤與圖片的核心邏輯 """
        try:
            t_num, t_tot = track["num"], len(meta['tracks'])
            track_artist = track.get("artist", meta["artist"])
            genre = meta.get("genre", "Unknown")
            
            # 讀取封面圖片 (二進位)
            cover_data = None
            is_png = False
            if meta.get("cover_path") and os.path.exists(meta["cover_path"]):
                try:
                    with open(meta["cover_path"], "rb") as f:
                        cover_data = f.read()
                    if meta["cover_path"].lower().endswith(".png"):
                        is_png = True
                except Exception as e:
                    print(f"Cover read error: {e}")

            # --- M4A (Apple Lossless / AAC) ---
            if fmt == 'm4a':
                f = MP4(filepath)
                # 清除舊標籤但保留某些原子結構
                try: f.delete()
                except: pass
                
                f["\xa9nam"] = track["title"]
                f["\xa9ART"] = track_artist
                f["aART"] = meta["artist"]
                f["\xa9alb"] = meta["album"]
                f["\xa9day"] = meta["year"]
                f["\xa9gen"] = genre
                f["trkn"] = [(int(t_num), t_tot)]
                
                if cover_data:
                    image_fmt = MP4Cover.FORMAT_PNG if is_png else MP4Cover.FORMAT_JPEG
                    f["covr"] = [MP4Cover(cover_data, imageformat=image_fmt)]
                f.save()

            # --- FLAC ---
            elif fmt == 'flac':
                f = FLAC(filepath)
                try: f.delete()
                except: pass
                
                f['title'] = track["title"]
                f['artist'] = track_artist
                f['albumartist'] = meta["artist"]
                f['album'] = meta["album"]
                f['date'] = meta["year"]
                f['genre'] = genre
                f['tracknumber'] = str(t_num)
                
                if cover_data:
                    p = Picture()
                    p.type = 3 # Front Cover
                    p.desc = 'Front Cover'
                    p.mime = 'image/png' if is_png else 'image/jpeg'
                    p.data = cover_data
                    f.add_picture(p)
                f.save()

            # --- MP3 (最容易出問題的部分) ---
            elif fmt == 'mp3':
                # 步驟 1: 寫入文字標籤 (使用 EasyMP3)
                try:
                    f = EasyMP3(filepath)
                except ID3NoHeaderError:
                    f = EasyMP3(filepath)
                    f.add_tags()
                
                f['title'] = track["title"]
                f['artist'] = track_artist
                f['albumartist'] = meta["artist"]
                f['album'] = meta["album"]
                f['date'] = meta["year"]
                f['genre'] = genre
                f['tracknumber'] = f"{t_num}/{t_tot}"
                f.save(v2_version=3) # 強制使用 ID3v2.3 以獲得最佳相容性

                # 步驟 2: 寫入圖片 (使用標準 ID3)
                if cover_data:
                    audio = ID3(filepath) # 重新開啟檔案以寫入 APIC
                    audio.add(APIC(
                        encoding=3, # UTF-8
                        mime='image/png' if is_png else 'image/jpeg',
                        type=3, # Front Cover
                        desc='Cover',
                        data=cover_data
                    ))
                    audio.save(v2_version=3)

        except Exception as e:
            # 這裡會把錯誤印在 console 方便除錯，若有 GUI log 可串接
            print(f"❌ Tagging Error for {filepath}: {e}")

    def eject_tray(self, drive):
        try: ctypes.windll.winmm.mciSendStringW(f"set {drive.replace(':', '')}: door open", None, 0, None)
        except: pass