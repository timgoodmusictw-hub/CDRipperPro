import os
import subprocess
import time
import ctypes
from mutagen.flac import FLAC
from mutagen.mp3 import EasyMP3
from mutagen.mp4 import MP4
from utils import resource_path, sanitize_filename
from config import FORMAT_SETTINGS, FREAC_EXE, FFMPEG_EXE

# 擴充 EasyMP3 的標籤支援 (如原本不支援 albumartist/genre 的舊版)
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
                "artist": "Unknown Artist", "album": f"Rip_{int(time.time())}", "year": time.strftime("%Y"), "genre": "Unknown",
                "tracks": [{"num": str(i+1), "title": f"Track {i+1:02d}", "artist": "Unknown Artist"} for i in range(99)]
            }

        # 資料夾使用 "Album Artist" 來歸檔
        save_path = os.path.join(output_root, target_fmt, sanitize_filename(metadata['artist']), sanitize_filename(metadata['album']))
        if not os.path.exists(save_path): os.makedirs(save_path)
        self.log(f"📂 輸出位置: {save_path}")

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
                if os.path.exists(wav_temp): os.remove(wav_temp)
                subprocess.run([self.freac_path, "-d", drive, "-t", str(t_num), "-o", wav_temp],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                
                if not os.path.exists(wav_temp): 
                    self.log(f"  ❌ 抓軌失敗"); continue

                cmd = [self.ffmpeg_path, "-y", "-i", wav_temp, "-c:a", fmt_cfg["codec"]] + fmt_cfg["extra_args"] + ["-vn", "-map_metadata", "-1", out_file]
                subprocess.run(cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

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
        try:
            t_num, t_tot = track["num"], len(meta['tracks'])
            track_artist = track.get("artist", meta["artist"]) # 取得單曲演出者，若無則用專輯演出者
            genre = meta.get("genre", "Unknown")

            if fmt == 'm4a':
                f = MP4(filepath); f.delete()
                f["\xa9nam"] = track["title"]
                f["\xa9ART"] = track_artist      # Track Artist
                f["aART"] = meta["artist"]       # Album Artist (重要：iTunes/iPhone 歸類用)
                f["\xa9alb"] = meta["album"]
                f["\xa9day"] = meta["year"]
                f["\xa9gen"] = genre             # Genre
                f["trkn"] = [(int(t_num), t_tot)]
                f.save()
            elif fmt == 'flac':
                f = FLAC(filepath); f.delete()
                f['title'] = track["title"]
                f['artist'] = track_artist       # Track Artist
                f['albumartist'] = meta["artist"] # Album Artist
                f['album'] = meta["album"]
                f['date'] = meta["year"]
                f['genre'] = genre
                f['tracknumber'] = str(t_num)
                f.save()
            elif fmt == 'mp3':
                try: f = EasyMP3(filepath)
                except: f = EasyMP3(filepath); f.add_tags()
                f['title'] = track["title"]
                f['artist'] = track_artist
                f['albumartist'] = meta["artist"]
                f['album'] = meta["album"]
                f['date'] = meta["year"]
                f['genre'] = genre
                f['tracknumber'] = f"{t_num}/{t_tot}"
                f.save()
        except Exception as e:
            print(f"Tag error: {e}")

    def eject_tray(self, drive):
        try: ctypes.windll.winmm.mciSendStringW(f"set {drive.replace(':', '')}: door open", None, 0, None)
        except: pass