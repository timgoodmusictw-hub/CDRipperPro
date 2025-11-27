import os

# --- 設定區 ---
DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Music", "Ripped")

# 工具檔名
FFMPEG_EXE = "ffmpeg.exe"
FREAC_EXE = "freaccmd.exe"
DISCID_DLL = "discid.dll"

# 格式參數
FORMAT_SETTINGS = {
    "m4a": {"codec": "alac", "extra_args": []},
    "flac": {"codec": "flac", "extra_args": ["-compression_level", "5"]},
    "mp3": {"codec": "libmp3lame", "extra_args": ["-b:a", "320k", "-id3v2_version", "3"]}
}

# User Agent
UA_APP = "MyPythonRipper"
UA_VER = "2.4"
UA_CONTACT = "contact@example.com"