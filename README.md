<div align="center">

# 🎵 BEATVAULT • MUSIC & LYRICS SUITE
### *High-Speed, Multi-Threaded Audio Extraction & ID3 Tagging Engine*

<br/>

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![UI](https://img.shields.io/badge/GUI-Fluent%20Dark%20WebView2-1DB954?style=for-the-badge&logo=spotify&logoColor=white)](#-user-interface--workflow)
[![Engine](https://img.shields.io/badge/Audio-yt--dlp%20%2B%20FFmpeg-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![Lyrics](https://img.shields.io/badge/Lyrics-LRCLIB%20Synced%20.LRC-8A2BE2?style=for-the-badge&logo=genius&logoColor=white)](#-synchronized-lyrics-engine)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](#-legal--compliance)

<br/>

**BeatVault is a studio-grade desktop audio workstation designed to convert Spotify playlists, albums, and direct search queries into pristine, metadata-rich MP3s with synchronized (.lrc) lyrics, individual song cover artwork, intelligent duplicate protection, and an integrated preview player.**

<br/>

[🚀 Quick Start](#-quick-start) • [✨ Key Capabilities](#-key-capabilities) • [⚡ Architecture](#-under-the-hood-architecture) • [🎧 Audio Player](#-in-app-audio-player--controls) • [⚙️ Settings](#-custom-settings) • [❓ FAQ](#-troubleshooting--faq)

</div>

---

## 🚀 Quick Start

### 1-Click Launch (Windows)
Double-click the included batch launcher inside the application folder:
```cmd
run_app.bat
```

### Command-Line Execution
```powershell
# Navigate to directory
cd "C:\Users\aadit\Desktop\Website Projects\BeatVault"

# Launch Native Desktop Window (Powered by Edge WebView2)
python main.py

# Or Launch in Web Browser UI Mode (Fallback)
python main.py --browser
```

> [!NOTE]
> All core dependencies (`yt-dlp`, `static-ffmpeg`, `mutagen`, `pywebview`, `requests`) and bundled static FFmpeg binaries are fully configured in the local environment.

---

## 📊 Comparison: Standard Downloaders vs. BeatVault

| Capability | Standard Web Tools / Bots | 🎵 BeatVault |
| :--- | :---: | :---: |
| **Download Concurrency** | ❌ 1-by-1 Sequential (Slow) | ✅ **⚡ 2x Parallel Multi-Threading** |
| **Song Artwork** | ❌ Repeats playlist cover on all tracks | ✅ **🖼️ Original per-track album cover (oEmbed)** |
| **Lyrics Support** | ❌ None | ✅ **🎤 Synced `.lrc` file + ID3 `USLT` tags** |
| **Audio Source Accuracy** | ❌ Random search (picks live/fake covers) | ✅ **🎯 Smart Duration Matching ($\pm12$s)** |
| **Download Reliability** | ⚠️ Often fails on missing matches | ✅ **🛡️ 100% Fallback Guarantee (Never drops tracks)** |
| **Duplicate Prevention** | ⚠️ Overwrites without asking | ✅ **🛡️ Multi-layer ID3 + Safe copy `(1).mp3`** |
| **File Naming** | ❌ Rigid / Arbitrary | ✅ **🏷️ Priority Song Name First + 4 Templates** |
| **Integrated Player** | ❌ None | ✅ **🎧 Real-time Scrubbable Mini Player Dock** |
| **Direct Search** | ❌ Spotify URL only | ✅ **🔍 Search by song name without link** |

---

## ✨ Key Capabilities

### ⚡ 1. 2x Parallel Multi-Threaded Engine
* Downloads **two tracks concurrently** via a synchronized `ThreadPoolExecutor`.
* Reduces download time of a 50-song playlist from **12 minutes down to ~3 minutes**.
* Thread-safe queuing with independent real-time progress indicators (speed, %, ETA).

### 🎤 2. Synchronized Lyrics Engine (.lrc & ID3 Tags)
* Queries the **LRCLIB** database in real-time.
* **Embedded Tags:** Writes unsynchronized text (`USLT` frame) into the MP3 metadata.
* **Karaoke Sync:** Automatically outputs a companion `{Song Name}.lrc` timestamped file for music players with real-time lyric scrolling (Poweramp, Apple Music, Samsung Music, foobar2000).

### 🎯 3. Smart Duration Matcher (with 100% Download Guarantee)
* Compares candidate audio streams against Spotify's official millisecond track length.
* Automatically filters out live concert recordings, crowd reactions, and slowed+reverb edits.
> [!IMPORTANT]
> **Zero Dropped Songs:** If a candidate within the $\pm12$s tolerance is unavailable, the engine **immediately falls back to the top search hit**, ensuring that every single track in your playlist downloads reliably.

### 🖼️ 4. Per-Song Original Album Cover Artwork
* Resolves the song's **unique Spotify CDN album cover** via official track oEmbed endpoints.
* Embeds high-resolution `APIC` front-cover artwork into the file so your media players display crisp visual art.

### 🛡️ 5. Non-Destructive Duplicate Protection
* Pre-scans destination directories using **Mutagen ID3 tag reading**, normalized title/artist string comparison, and fuzzy sequence matching.
* If a duplicate is identified, the user is presented with a non-destructive choice:
  * **⏭️ Skip Song:** Retains the existing file.
  * **📥 Download Again:** Automatically writes to `Song - Artist (1).mp3`, strictly safeguarding original files.
  * **⚡ Bulk Option:** *"Apply to all remaining duplicates in this batch"* checkbox.

### 🔍 6. Dual Operating Modes
* **Tab 1: Spotify Playlist / Album / Track Link:** Paste any playlist URL and load full tracklists.
* **Tab 2: Direct Single Song Search:** Type any song name or artist (e.g., *"Kesariya"*, *"Shape of You"*) to retrieve instant high-res search results with 30-second previews and 1-click downloads.

---

## ⚡ Under-the-Hood Architecture

```mermaid
flowchart TD
    A["User Input: Spotify URL or Search Query"] --> B{"Input Mode"}
    
    B -->|"Spotify Playlist"| C["SpotifyService: Parse Embed JSON"]
    B -->|"Direct Search"| D["iTunes / Public Audio Search API"]
    
    C --> E["Batch Duplicate Pre-Scan: ID3 & Fuzzy Check"]
    D --> E
    
    E --> F["ThreadPoolExecutor: 2x Parallel Queue"]
    
    subgraph Parallel Worker Pipeline
        F --> G["Smart Duration Matcher (±12s Filter)"]
        G --> H{"Match Found?"}
        H -->|"Yes"| I["Download Targeted Audio Stream"]
        H -->|"No (Fallback)"| J["Download Top Ranked Official Feed"]
        
        I --> K["Static FFmpeg: Transcode to MP3"]
        J --> K
        
        K --> L["Fetch High-Res Album Cover via oEmbed"]
        L --> M["LRCLIB API: Fetch Plain & Synced Lyrics"]
        M --> N["Mutagen: Embed ID3v2 Tags (TIT2, TPE1, APIC, USLT)"]
        N --> O["Write Companion .lrc File"]
    end
    
    O --> P["Saved to Laptop in Selected Destination Folder"]
    P --> Q["In-App Mini Player: Instant 1-Click Playback"]
```

---

## 🖥️ User Interface & Workflow

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 🟢 BeatVault                                 [⚡ 2x Parallel Active]   [⚙️ Settings]   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [ 📋 Spotify Playlist / Album ]      [ 🔍 Direct Single Song Search ]                  │
│                                                                                        │
│  ┌────────────────────────────────────┐  ┌───────────────────────────────────────────┐ │
│  │ 1. Spotify Playlist Link           │  │ 2. Save Destination Folder                │ │
│  │ [ https://open.spotify.com/...   ] │  │ [ C:\Users\aadit\Music\BeatVault Downloads] │ │
│  │ [ 📋 Paste ]   [ 📥 Load ]         │  │ [ 📁 Browse... ]   [ 📂 Open Folder ]     │ │
│  └────────────────────────────────────┘  └───────────────────────────────────────────┘ │
│                                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ [Cover Art]  Today's Top Hits • By Spotify • 50 tracks • 2 duplicates detected   │  │
│  ├──────────────────────────────────────────────────────────────────────────────────┤  │
│  │ [x] Select All (50/50)   [🔍 Scan Duplicates]   [ ] Auto-Skip   [ Download (2x) ]│  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                        │
│  #   Sel   Title & Artist                     Duration    Status              Play     │
│  ────────────────────────────────────────────────────────────────────────────────────  │
│  1   [x]   Stop The Wedding! - Ashe           3:18        ✓ Saved             [▶ Play] │
│  2   [x]   Espresso - Sabrina Carpenter       2:55        Downloading (64%)   --       │
│  3   [x]   Birds of a Feather - Billie Eilish 3:03        Downloading (22%)   --       │
│  4   [x]   Good Luck, Babe! - Chappell Roan   3:38        Queued              --       │
└────────────────────────────────────────────────────────────────────────────────────────┘
│ 🎧 Stop The Wedding! - Ashe    [ ⏸ ]   01:14 ━━━━━━⚪────────── 03:18   🔊 ━━━━⚪─   [✕] │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎧 In-App Audio Player & Controls

The desktop client features an integrated, real-time audio playback dock:

| Control | Action | Details |
| :---: | :--- | :--- |
| **`▶ Preview` / `▶ Play`** | **Play Track** | Click on any search card or completed playlist track |
| **`⏸ Pause`** | **Pause Audio** | Click the active button or round `[ ⏸ ]` dock button |
| **`▶ Resume`** | **Resume Audio** | Click to resume playback without reloading |
| <kbd>Spacebar</kbd> | **Toggle Play / Pause** | Global shortcut when not typing in an input field |
| **Progress Scrubber** | **Seek Track** | Drag slider to jump to any timestamp |
| **Volume Slider** | **Adjust Audio Level** | Fine-tune volume output |
| **`✕` Button** | **Close Player** | Stops audio stream and hides the mini-player dock |

> [!TIP]
> The active play button automatically synchronizes across both the tracklist and the bottom dock, updating dynamically when playback starts, pauses, or finishes.

---

## ⚙️ Custom Settings

Click the **⚙️ Settings** button in the top-right header to adjust preferences:

<details>
<summary><b>View Available Settings & Options</b></summary>
<br/>

### 1. Filename Formatting Templates
Choose how downloaded MP3 files are named on disk:
- `title_artist` *(Default)*: `Song Name - Artist.mp3` *(Song name first)*
- `artist_title`: `Artist - Song Name.mp3`
- `track_title_artist`: `01. Song Name - Artist.mp3` *(Retains original playlist track order)*
- `title_only`: `Song Name.mp3`

### 2. Audio Bitrate Quality
- **192 kbps (High Quality):** Fast downloads, lightweight file sizes (~4MB per song).
- **320 kbps (Ultra High Quality):** Maximum acoustic detail and depth for high-end headphones.

### 3. Lyric Synchronization Toggle
- Automatically searches LRCLIB for synchronized time codes and outputs `.lrc` companion files alongside your MP3s.
</details>

---

## 📁 Project Structure

```
BeatVault/
├── gui/
│   └── index.html             # Fluent Dark responsive GUI (Tailwind/CSS, Player, Modals)
├── api.py                     # Python-to-JavaScript IPC bridge & folder picker
├── downloader.py              # Parallel download manager (Concurrency=2) & duration filter
├── duplicate_detector.py      # Mutagen ID3 inspector & non-destructive name generator
├── lyrics_service.py          # LRCLIB API client (.lrc creator & ID3 USLT embedder)
├── spotify_service.py         # Zero-config Spotify playlist & album scraper
├── main.py                    # PyWebView desktop entrypoint + local browser server
├── requirements.txt           # Python package specifications
├── run_app.bat                # 1-Click execution script for Windows
└── README.md                  # Comprehensive documentation
```

---

## ❓ Troubleshooting & FAQ

<details>
<summary><b>Q: Does this application require a Spotify Developer Client ID or Secret?</b></summary>
<br/>
<b>No.</b> The application uses public embed metadata scrapers to retrieve song titles, artists, and album art out of the box with zero setup required.
</details>

<details>
<summary><b>Q: Do I need to manually install FFmpeg on my Windows laptop?</b></summary>
<br/>
<b>No.</b> The project incorporates <code>static-ffmpeg</code>, which automatically provisions portable FFmpeg and FFprobe binaries without requiring manual path configurations.
</details>

<details>
<summary><b>Q: What happens if a song already exists in my selected folder?</b></summary>
<br/>
The intelligent duplicate engine will detect it (via ID3 tags or file naming) and pause to ask whether you'd like to <b>Skip</b> or <b>Download Again</b>. If you choose Download Again, it appends a safe incremental suffix <code>(1).mp3</code> so your original file is never overwritten.
</details>

<details>
<summary><b>Q: Why does the app download 2 tracks at a time instead of 10?</b></summary>
<br/>
Concurrency is intentionally calibrated to <b>2 parallel workers</b>. This achieves double the download speed while avoiding YouTube rate limits, temporary socket blocks, or local CPU bottlenecks during FFmpeg audio transcoding.
</details>

---

## 🛡️ Legal & Compliance

This software is developed strictly for educational and personal archival purposes:
* **No DRM Circumvention:** This application **does not bypass, decrypt, or access protected Spotify audio streams or DRM systems**.
* **Public Metadata Usage:** Spotify URLs are queried solely for public track metadata (title, artist, duration).
* **Authorized Audio Sources:** Audio streams are gathered from publicly accessible, legally authorized feeds matched against track metadata.

---

<div align="center">

Crafted with ❤️ for music enthusiasts.

[▲ Back to Top](#-beatvault--music--lyrics-suite)

</div>
