import os
import sys
import time
import ctypes
import urllib.request
import urllib.parse
import subprocess
import requests
import urllib3
import json
import musicbrainzngs
import wmi
from ctypes import c_char_p, c_int, c_void_p
from utils import resource_path
from config import DISCID_DLL, UA_APP, UA_VER, UA_CONTACT

# --- [設定] 是否啟用除錯日誌 ---
# True = 發生錯誤時寫入 debug_log.txt
# False = 忽略錯誤 (正式發布建議設為 False)
ENABLE_DEBUG_LOG = False
# -----------------------------

# 忽略 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

musicbrainzngs.set_useragent(UA_APP, UA_VER, UA_CONTACT)

def get_base_path():
    """ 取得執行檔所在的真實目錄 """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def log_error(msg):
    """ 將錯誤寫入 debug_log.txt 以便除錯 """
    # [修改處] 檢查開關變數
    if not ENABLE_DEBUG_LOG: return

    log_path = os.path.join(get_base_path(), "debug_log.txt")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except: pass

class DiscIDWrapper:
    """ MusicBrainz DiscID 讀取器 """
    def __init__(self, dll_name=DISCID_DLL):
        self.dll_path = resource_path(os.path.join("tools", dll_name))
        self.lib = None
        try:
            self.lib = ctypes.cdll.LoadLibrary(self.dll_path)
            self.lib.discid_new.restype = c_void_p
            self.lib.discid_free.argtypes = [c_void_p]
            self.lib.discid_read_sparse.argtypes = [c_void_p, c_char_p, c_int]; self.lib.discid_read_sparse.restype = c_int
            self.lib.discid_get_id.argtypes = [c_void_p]; self.lib.discid_get_id.restype = c_char_p
            self.lib.discid_get_freedb_id.argtypes = [c_void_p]; self.lib.discid_get_freedb_id.restype = c_char_p
            self.lib.discid_get_first_track_num.argtypes = [c_void_p]; self.lib.discid_get_first_track_num.restype = c_int
            self.lib.discid_get_last_track_num.argtypes = [c_void_p]; self.lib.discid_get_last_track_num.restype = c_int
            self.lib.discid_get_track_offset.argtypes = [c_void_p, c_int]; self.lib.discid_get_track_offset.restype = c_int
            self.lib.discid_get_sectors.argtypes = [c_void_p]; self.lib.discid_get_sectors.restype = c_int
            self.disc = self.lib.discid_new()
        except Exception as e:
            self.lib = None
            log_error(f"DiscID Init Error: {e}")

    def read_drive(self, drive_letter):
        if not self.lib: return False
        drive_str = drive_letter if ":" in drive_letter else f"{drive_letter}:"
        try: return self.lib.discid_read_sparse(self.disc, drive_str.encode('utf-8'), 0) != 0
        except: return False

    def get_mb_discid(self): return self.lib.discid_get_id(self.disc).decode('utf-8') if self.lib else None

    def get_track_count(self):
        if not self.lib: return 0
        try: return self.lib.discid_get_last_track_num(self.disc) - self.lib.discid_get_first_track_num(self.disc) + 1
        except: return 0

    def get_freedb_data(self):
        if not self.lib: return None
        try:
            fid = self.lib.discid_get_freedb_id(self.disc).decode('utf-8')
            first = self.lib.discid_get_first_track_num(self.disc); last = self.lib.discid_get_last_track_num(self.disc)
            return {"discid": fid, "track_count": str(last - first + 1), "offsets": [str(self.lib.discid_get_track_offset(self.disc, i)) for i in range(first, last + 1)], "seconds": str(self.lib.discid_get_sectors(self.disc) // 75)}
        except: return None

class CDDBQueryEngine:
    """ 通用 CDDB 查詢引擎 """
    def __init__(self, server_url, name):
        self.server_url = server_url
        self.name = name
    
    def query(self, disc_data, log_func):
        if not disc_data: return None
        
        # 建立 CDDB 查詢指令
        cmd_arg = f"cddb query {disc_data['discid']} {disc_data['track_count']} {' '.join(disc_data['offsets'])} {disc_data['seconds']}"
        params = {'cmd': cmd_arg, 'hello': 'user host client 1.0', 'proto': '6'}
        query_url = f"{self.server_url}?{urllib.parse.urlencode(params)}"
        
        try:
            log_func(f"  📡 連線 {self.name}...")
            resp = requests.get(query_url, timeout=10, verify=False)
            content = resp.text
            
            parts = content.split()
            if not parts: return None
            
            try:
                code = int(parts[0])
            except: return None
            
            cat, disc_id = "", ""
            
            if code == 200: 
                cat, disc_id = parts[1], parts[2]
            elif code in (210, 211): 
                lines = content.strip().split('\n')
                if len(lines) > 1:
                    target_parts = lines[1].split()
                    cat, disc_id = target_parts[0], target_parts[1]
                else: return None
            else: 
                return None

            log_func(f"  📖 {self.name} 讀取: {cat}")
            
            # 讀取詳細資料
            read_cmd = f"cddb read {cat} {disc_id}"
            read_params = {'cmd': read_cmd, 'hello': 'u h c 1.0', 'proto': '6'}
            read_url = f"{self.server_url}?{urllib.parse.urlencode(read_params)}"
            
            resp_read = requests.get(read_url, timeout=10, verify=False)
            raw_data = resp_read.content 
            
            decoded_text = ""
            for enc in ['utf-8', 'shift_jis', 'cp1252', 'iso-8859-1', 'gbk']:
                try: 
                    decoded_text = raw_data.decode(enc)
                    break
                except: continue
            
            return self.parse_entry(decoded_text)
            
        except Exception as e:
            log_error(f"{self.name} Query Error: {e}")
            return None

    def parse_entry(self, text):
        info = {"artist": "Unknown", "album": "Unknown", "year": time.strftime("%Y"), "genre": "Unknown", "tracks": []}
        track_titles = {}
        for line in text.strip().split('\n'):
            line = line.strip()
            if line.startswith("DTITLE="):
                full = line[7:]
                if " / " in full: info["artist"], info["album"] = full.split(" / ", 1)
                else: info["album"] = full
            elif line.startswith("DYEAR="): info["year"] = line[6:]
            elif line.startswith("DGENRE="): info["genre"] = line[7:]
            elif line.startswith("TTITLE"):
                try: 
                    k, v = line.split("=", 1); track_idx = int(k.replace("TTITLE", ""))
                    track_titles[track_idx] = v
                except: pass
        for i in sorted(track_titles.keys()):
            info["tracks"].append({"num": str(i + 1), "title": track_titles[i], "artist": info["artist"]})
        return info

class NativeCDReader:
    @staticmethod
    def get_cd_info(drive_letter):
        # 維持不變
        ps = f"""
        $ErrorActionPreference='SilentlyContinue'; [Console]::OutputEncoding=[System.Text.Encoding]::UTF8
        $wmp=New-Object -ComObject WMPlayer.OCX; $drives=$wmp.cdromCollection
        $target='{drive_letter}'; if($target.Length -eq 1){{$target=$target+':'}}
        for($i=0;$i -lt $drives.count;$i++){{
            $cd=$drives.item($i); if($cd.driveSpecifier -eq $target -and $cd.playlist.count -gt 0){{
                Write-Output ("ALBUM::"+$cd.playlist.name)
                for($j=0;$j -lt $cd.playlist.count;$j++){{
                    $t=$cd.playlist.item($j); 
                    Write-Output ("TRACK::"+$t.name+"::"+$t.getItemInfo("Artist")+"::"+$t.getItemInfo("Genre"))
                }}
            }}
        }}"""
        try:
            res = subprocess.run(["powershell", "-Command", ps], capture_output=True, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
            lines = res.stdout.strip().split('\n')
            if not lines: return None
            
            info = {"artist": "Various Artists", "album": "Unknown", "year": time.strftime("%Y"), "genre": "Unknown", "tracks": []}
            artists = []; genres = []
            for line in lines:
                if line.startswith("ALBUM::"): info["album"] = line.replace("ALBUM::", "")
                elif line.startswith("TRACK::"):
                    parts = line.split("::")
                    title = parts[1] if len(parts) > 1 else "Unknown"
                    art = parts[2] if len(parts) > 2 and parts[2] else ""
                    gen = parts[3] if len(parts) > 3 and parts[3] else ""
                    if art: artists.append(art)
                    if gen: genres.append(gen)
                    info["tracks"].append({"num": str(len(info["tracks"]) + 1), "title": title, "artist": art})
            from collections import Counter
            if artists: 
                common_art = Counter(artists).most_common(1)
                if common_art: info["artist"] = common_art[0][0]
            if genres:
                common_gen = Counter(genres).most_common(1)
                if common_gen: info["genre"] = common_gen[0][0]
            for t in info["tracks"]:
                if not t["artist"]: t["artist"] = info["artist"]
            if info["tracks"] and "Track" in info["tracks"][0]["title"] and info["album"].startswith("Album"): return None
            return info
        except: return None

class MetadataManager:
    def __init__(self, logger_func):
        self.log = logger_func
        self.disc_reader = DiscIDWrapper()
        
        self.cddb_sources = [
            CDDBQueryEngine("http://gnudb.gnudb.org/~cddb/cddb.cgi", "GnuDB"),
            CDDBQueryEngine("http://freedb.dbpoweramp.com/~cddb/cddb.cgi", "FreeDB (dbPowerAmp)"),
            CDDBQueryEngine("http://tracktype.org/~cddb/cddb.cgi", "FreeDB (TrackType)")
        ]

    def check_dependency(self): return self.disc_reader.lib is not None
    
    def get_cd_drives(self):
        drives = []
        try: 
            for d in wmi.WMI().Win32_CDROMDrive(): drives.append(d.Drive)
        except: 
            import string; drives = ['%s:' % d for d in string.ascii_uppercase if os.path.exists('%s:' % d)]
        return drives

    def _ensure_tracks(self, info, physical_count):
        if not info: return None
        if "artist" not in info: info["artist"] = "Unknown Artist"
        if "album" not in info: info["album"] = "Unknown Album"
        if "genre" not in info: info["genre"] = "Unknown"
        if "year" not in info: info["year"] = time.strftime("%Y")
        if "tracks" not in info: info["tracks"] = []
        if len(info["tracks"]) == 0:
            info["tracks"] = [{"num": str(i + 1), "title": f"Track {i+1:02d}", "artist": info["artist"]} for i in range(physical_count)]
        for t in info["tracks"]:
            if "artist" not in t or not t["artist"]: t["artist"] = info["artist"]
        return info

    def download_cover(self, release_id):
        if not release_id: return None
        try:
            api_url = f"https://coverartarchive.org/release/{release_id}/"
            resp = requests.get(api_url, timeout=10, verify=False)
            if resp.status_code != 200: return None
            data = resp.json()
            if "images" in data and len(data["images"]) > 0:
                img_url = None
                for img in data["images"]:
                    if "Front" in img.get("types", []) or img.get("front", False):
                        img_url = img["image"]
                        break
                if not img_url: img_url = data["images"][0]["image"]
                if img_url.startswith("http://"): img_url = img_url.replace("http://", "https://")
                
                self.log("  🖼️ 發現封面，正在下載...")
                r = requests.get(img_url, stream=True, timeout=15, verify=False)
                if r.status_code == 200:
                    temp_path = os.path.join(get_base_path(), "temp_cover.jpg")
                    with open(temp_path, 'wb') as f:
                        for chunk in r.iter_content(1024): f.write(chunk)
                    return temp_path
        except Exception as e:
            log_error(f"Cover Download Exception: {e}")
        return None

    def fetch(self, drive_letter, use_native_first=False):
        if not self.disc_reader.read_drive(drive_letter):
            self.log("❌ 無法讀取光碟結構"); return None
        
        physical_count = self.disc_reader.get_track_count()
        if physical_count == 0: physical_count = 15

        if use_native_first:
            self.log("💿 讀取 CD-Text...")
            if info := NativeCDReader.get_cd_info(drive_letter):
                self.log(f"✅ CD-Text: {info['album']}")
                info["cover_path"] = None
                return self._ensure_tracks(info, physical_count)

        self.log("🔍 查詢 MusicBrainz...")
        try:
            if mb_id := self.disc_reader.get_mb_discid():
                res = musicbrainzngs.get_releases_by_discid(mb_id, includes=["artists", "recordings"])
                if "disc" in res and "release-list" in res["disc"]:
                    rel = res["disc"]["release-list"][0]
                    release_id = rel["id"]
                    cover_file = self.download_cover(release_id)
                    
                    info = {
                        "artist": rel["artist-credit"][0]["artist"]["name"],
                        "album": rel.get("title", "Unknown"),
                        "year": rel.get("date", "0000").split("-")[0],
                        "genre": "Unknown",
                        "tracks": [],
                        "cover_path": cover_file
                    }
                    if info["cover_path"]: self.log("  ✅ 封面下載成功")

                    for t in rel["medium-list"][0]["track-list"]:
                        track_artist = t["recording"].get("artist-credit", [{"artist": {"name": info["artist"]}}])[0]["artist"]["name"]
                        info["tracks"].append({"num": t["number"], "title": t["recording"]["title"], "artist": track_artist})
                    
                    self.log(f"✅ MusicBrainz: {info['album']}")
                    return self._ensure_tracks(info, physical_count)
        except Exception as e:
            self.log(f"  ⚠️ MusicBrainz 失敗: {e}")

        self.log("🔍 查詢 CDDB (GnuDB / FreeDB)...")
        if disc_data := self.disc_reader.get_freedb_data():
            for source in self.cddb_sources:
                info = source.query(disc_data, self.log)
                
                if info:
                    if info.get("artist") == "Unknown" and info.get("album") == "Unknown":
                        self.log(f"  ⚠️ {source.name} 資料無效 (Unknown)，嘗試下一來源...")
                        continue
                        
                    self.log(f"✅ {source.name}: {info['album']}")
                    info["cover_path"] = None
                    return self._ensure_tracks(info, physical_count)

        if not use_native_first:
            self.log("🔄 嘗試 CD-Text...")
            if info := NativeCDReader.get_cd_info(drive_letter):
                info["cover_path"] = None
                return self._ensure_tracks(info, physical_count)

        self.log("⚠️ 無資料"); 
        return self._ensure_tracks({"artist": "Unknown", "album": "Unknown", "cover_path": None, "tracks": []}, physical_count)