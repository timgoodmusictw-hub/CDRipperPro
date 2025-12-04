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
        drive_arg = drive 

        if not metadata:
            metadata = {
                "artist": "Unknown Artist", "album": f"Rip_{int(time.time())}", "year": time.strftime("%Y"), "genre": "Unknown", 
                "disc": "1", "total_discs": "1", "cover_path": None,
                "tracks": [{"num": str(i+1), "title": f"Track {i+1:02d}", "artist": "Unknown Artist"} for i in range(99)]
            }

        # 路徑邏輯
        base_path = os.path.join(output_root, target_fmt, sanitize_filename(metadata['artist']), sanitize_filename(metadata['album']))
        try:
            total_discs = int(metadata.get('total_discs', '1'))
            disc_num = int(metadata.get('disc', '1'))
        except:
            total_discs = 1; disc_num = 1

        if total_discs > 1: save_path = os.path.join(base_path, f"CD{disc_num}")
        else: save_path = base_path

        if not os.path.exists(save_path): os.makedirs(save_path)
        self.log(f"📂 輸出位置: {save_path}")

        if metadata.get("cover_path") and os.path.exists(metadata["cover_path"]):
            self.log(f"  🖼️ 準備嵌入封面: {os.path.basename(metadata['cover_path'])}")

        total = len(metadata['tracks'])
        for track in metadata['tracks']:
            if self.stop_flag: break
            t_num = int(track['num'])
            t_title = track['title']
            
            fname = f"{t_num:02d}. {sanitize_filename(t_title)}.{target_fmt}"
            out_file = os.path.join(save_path, fname)
            wav_temp = os.path.abspath(os.path.join(os.getcwd(), f"temp_{t_num}.wav"))

            self.log(f"💿 [{t_num}/{total}] 處理: {t_title}")
            try:
                if os.path.exists(wav_temp): os.remove(wav_temp)
                process = subprocess.run(
                    [self.freac_path, "-d", drive_arg, "-t", str(t_num), "-o", wav_temp],
                    capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW
                )
                if not os.path.exists(wav_temp): 
                    err_msg = process.stderr.strip() if process.stderr else "無錯誤回傳"
                    if "No disc" in err_msg: short_err = "找不到光碟"
                    elif "Drive not ready" in err_msg: short_err = "光碟機未就緒"
                    else: short_err = err_msg[:50]
                    self.log(f"  ❌ 失敗: {short_err}"); continue

                cmd = [self.ffmpeg_path, "-y", "-i", wav_temp, "-c:a", fmt_cfg["codec"]] + fmt_cfg["extra_args"] + ["-vn", "-map_metadata", "-1", out_file]
                subprocess.run(cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

                if os.path.exists(out_file):
                    self.write_tags(out_file, metadata, track, target_fmt)
                    self.log(f"  ✅ 完成")
            except Exception as e:
                self.log(f"  ❌ 程式錯誤: {e}")
            finally:
                if os.path.exists(wav_temp): os.remove(wav_temp)

        # [新增] 轉檔結束後，嘗試刪除暫存封面
        self._cleanup_temp_cover(metadata)

        if not self.stop_flag:
            self.log("🎉 全部完成！"); self.eject_tray(drive)

    def _cleanup_temp_cover(self, metadata):
        """ 清除暫存封面檔 (僅限自動下載的 temp_cover.jpg) """
        try:
            if metadata and metadata.get("cover_path"):
                path = metadata["cover_path"]
                # 安全檢查：只刪除檔名為 temp_cover.jpg 的檔案
                if os.path.basename(path) == "temp_cover.jpg" and os.path.exists(path):
                    # 嘗試刪除，如果被佔用則忽略
                    try: os.remove(path)
                    except: pass
        except: pass

    def write_tags(self, filepath, meta, track, fmt):
        try:
            t_num, t_tot = track["num"], len(meta['tracks'])
            track_artist = track.get("artist", meta["artist"])
            genre = meta.get("genre", "Unknown")
            disc_num = meta.get("disc", "1")
            total_discs = meta.get("total_discs", "1")

            cover_data = None
            is_png = False
            if meta.get("cover_path") and os.path.exists(meta["cover_path"]):
                try:
                    with open(meta["cover_path"], "rb") as f:
                        cover_data = f.read()
                    if meta["cover_path"].lower().endswith(".png"): is_png = True
                except: pass

            if fmt == 'm4a':
                f = MP4(filepath); 
                try: f.delete()
                except: pass
                f["\xa9nam"] = track["title"]; f["\xa9ART"] = track_artist
                f["aART"] = meta["artist"]; f["\xa9alb"] = meta["album"]
                f["\xa9day"] = meta["year"]; f["\xa9gen"] = genre
                f["trkn"] = [(int(t_num), t_tot)]
                f["disk"] = [(int(disc_num), int(total_discs))]
                if cover_data:
                    img_fmt = MP4Cover.FORMAT_PNG if is_png else MP4Cover.FORMAT_JPEG
                    f["covr"] = [MP4Cover(cover_data, imageformat=img_fmt)]
                f.save()

            elif fmt == 'flac':
                f = FLAC(filepath); 
                try: f.delete()
                except: pass
                f['title'] = track["title"]; f['artist'] = track_artist
                f['albumartist'] = meta["artist"]; f['album'] = meta["album"]
                f['date'] = meta["year"]; f['genre'] = genre
                f['tracknumber'] = str(t_num)
                f['discnumber'] = str(disc_num)
                f['totaldiscs'] = str(total_discs)
                if cover_data:
                    p = Picture(); p.type = 3; p.desc = 'Front Cover'
                    p.mime = 'image/png' if is_png else 'image/jpeg'
                    p.data = cover_data
                    f.add_picture(p)
                f.save()

            elif fmt == 'mp3':
                try: f = EasyMP3(filepath)
                except ID3NoHeaderError: f = EasyMP3(filepath); f.add_tags()
                f['title'] = track["title"]; f['artist'] = track_artist
                f['albumartist'] = meta["artist"]; f['album'] = meta["album"]
                f['date'] = meta["year"]; f['genre'] = genre
                f['tracknumber'] = f"{t_num}/{t_tot}"
                f['discnumber'] = f"{disc_num}/{total_discs}"
                f.save(v2_version=3)
                if cover_data:
                    audio = ID3(filepath)
                    audio.add(APIC(encoding=3, mime='image/png' if is_png else 'image/jpeg', type=3, desc='Cover', data=cover_data))
                    audio.save(v2_version=3)
        except Exception as e:
            print(f"❌ Tagging Error: {e}")

    def eject_tray(self, drive):
        try: ctypes.windll.winmm.mciSendStringW(f"set {drive.replace(':', '')}: door open", None, 0, None)
        except: pass