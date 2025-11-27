# CDRipperPro - CD 轉檔工具 (CD Ripper)

**CDRipperPro** ，一個輕量、模組化且功能強大的 CD 音訊擷取（抓軌）工具。它結合了 MusicBrainz 與 GnuDB (FreeDB) 資料庫，能自動搜尋專輯封面與曲目資訊，並支援手動編輯每一首歌曲的詳細資料（如個別演出者、流派等）。

**CDRipperPro** is a lightweight, modular, and powerful CD audio extraction tool. It integrates MusicBrainz and GnuDB (FreeDB) databases to automatically fetch album metadata and supports manual editing for individual track details (e.g., specific artists, genres).

-----

## 🇹🇼 繁體中文說明

### ✨ 主要功能

  * **多重資料來源**：自動從 **MusicBrainz**、**GnuDB (FreeDB)** 搜尋專輯資訊，並支援讀取 **CD-Text**。
  * **完整編輯功能**：
      * 若線上無資料，自動建立空白模板。
      * 支援修改專輯名稱、年份、流派 (Genre)。
      * **個別曲目編輯**：可針對每一首歌單獨設定歌名與演出者 (Artist)，適合處理合輯 (Compilation) 或原聲帶 (OST)。
  * **多種格式支援**：支援轉檔為 **FLAC** (無損)、**M4A** (Apple Lossless) 與 **MP3** (320k)。
  * **自動寫入標籤**：轉檔後自動將 ID3/Vorbis 標籤寫入檔案，包含 Album Artist 與 Track Artist 的區別。
  * **模組化設計**：程式碼結構清晰，易於維護與擴充。

### 📂 系統需求與安裝

本程式依賴 Python 3 以及部分外部執行檔。

#### 1\. Python 套件安裝

請確保已安裝 Python 3.8+，並執行以下指令安裝依賴庫：

```bash
pip install wmi musicbrainzngs mutagen
```

*(注意：Windows 用戶需安裝 `pywin32` 以支援 WMI)*

#### 2\. 外部工具 (Tools 資料夾)

程式根目錄下必須包含一個名為 `tools` 的資料夾，並放入以下檔案：

  * `ffmpeg.exe` (用於音訊編碼)
  * `freaccmd.exe` (用於 CD 抓軌)
  * `discid.dll` (用於計算光碟 ID)

### 🚀 如何使用

1.  執行 `main.py` 啟動程式：
    ```bash
    python main.py
    ```
2.  **選擇光碟機**：在上方選單選擇含有 CD 的光碟機代號，點擊「重整」若未出現。
3.  **搜尋資訊**：
      * 點擊 **「1. 搜尋資訊」**。
      * 程式將依序查詢 MusicBrainz -\> GnuDB -\> CD-Text。
      * 若皆無資料，會自動產生「Track 01, Track 02...」的空白列表。
4.  **編輯內容 (選用)**：
      * 點擊 **「2. 編輯資訊」**。
      * 在此視窗中，你可以修改專輯名稱、年份、流派。
      * 在下方列表中，可以修改每一軌的歌名與演出者。
5.  **開始轉檔**：
      * 選擇輸出格式 (FLAC/M4A/MP3) 與輸出路徑。
      * 點擊 **「3. 開始轉檔」**，程式將自動抓軌並寫入標籤。

### 🏗️ 專案結構

  * `main.py`: 程式進入點。
  * `ui.py`: 圖形介面 (GUI) 與編輯視窗邏輯。
  * `metadata.py`: 處理 DiscID、MusicBrainz、GnuDB 與 CD-Text 的資料讀取。
  * `engine.py`: 負責呼叫 `freac` 與 `ffmpeg` 進行轉檔與標籤寫入。
  * `config.py`: 全域設定檔。
  * `utils.py`: 通用工具函式。

-----

## 🇺🇸 English Instructions

### ✨ Key Features

  * **Multi-Source Metadata**: Automatically fetches album info from **MusicBrainz**, **GnuDB (FreeDB)**, and reads local **CD-Text**.
  * **Comprehensive Editing**:
      * Automatically generates a blank template if no online data is found.
      * Supports editing Album Name, Year, and **Genre**.
      * **Per-Track Editing**: Allows individual setting of Title and Artist for each track, perfect for Compilations or OSTs.
  * **Format Support**: Converts to **FLAC** (Lossless), **M4A** (ALAC), and **MP3** (320k).
  * **Auto-Tagging**: Automatically writes ID3/Vorbis tags after conversion, correctly handling Album Artist vs. Track Artist.
  * **Modular Design**: Clean code structure for easy maintenance and expansion.

### 📂 Requirements & Installation

This program requires Python 3 and several external binaries.

#### 1\. Python Libraries

Ensure you have Python 3.8+ installed, then run:

```bash
pip install wmi musicbrainzngs mutagen
```

*(Note: Windows users also need `pywin32` for WMI support)*

#### 2\. External Tools (Tools Folder)

You must create a folder named `tools` in the root directory and place the following files inside:

  * `ffmpeg.exe` (For audio encoding)
  * `freaccmd.exe` (For CD ripping)
  * `discid.dll` (For DiscID calculation)

### 🚀 Usage Guide

1.  Run `main.py` to start the application:
    ```bash
    python main.py
    ```
2.  **Select Drive**: Choose your CD drive from the dropdown menu. Click "Refresh" if it doesn't appear.
3.  **Fetch Info**:
      * Click **"1. Search Info"**.
      * The app will query MusicBrainz -\> GnuDB -\> CD-Text in order.
      * If no data is found, it generates a generic list (Track 01, Track 02...) based on physical tracks.
4.  **Edit Metadata (Optional)**:
      * Click **"2. Edit Info"**.
      * In this window, you can modify the Album, Year, and Genre.
      * You can also edit the Title and Artist for every single track independently.
5.  **Start Ripping**:
      * Select your desired format (FLAC/M4A/MP3) and output directory.
      * Click **"3. Start Rip"**. The program will rip, convert, and tag your files.

### 🏗️ Project Structure

  * `main.py`: Entry point of the application.
  * `ui.py`: GUI logic and the Track Editor dialog.
  * `metadata.py`: Handles fetching data from DiscID, MusicBrainz, GnuDB, and CD-Text.
  * `engine.py`: Handles audio processing (calling `freac`/`ffmpeg`) and tag writing.
  * `config.py`: Global configuration and constants.
  * `utils.py`: Utility functions.

-----

*Created by [tim_good_music@Threads]*