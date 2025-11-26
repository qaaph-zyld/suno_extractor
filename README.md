# 🎵 Suno Extractor Pro

A comprehensive toolkit for managing your Suno AI music library. Extract, download, organize, analyze, and play your AI-generated music collection.

![Version](https://img.shields.io/badge/version-3.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## ✨ Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **🔍 Smart Extraction** | Connect to existing Chrome session, extract all songs with metadata |
| **📥 Audio Download** | Download MP3/M4A/WAV files directly from Suno CDN |
| **🏷️ ID3 Tagging** | Automatic metadata embedding (title, artist, cover art, lyrics) |
| **🎵 Music Player** | Built-in terminal player with playback controls |
| **📋 Playlist Export** | Create M3U playlists for any media player |
| **🔎 Search & Filter** | Query your local collection by title, tags, lyrics |
| **📊 Analytics** | Statistics dashboard for your music library |
| **💻 Rich CLI** | Beautiful command-line interface with colors and tables |

### New in v3.0

| Feature | Description |
|---------|-------------|
| **🌐 Web Dashboard** | Beautiful Flask-based local web UI with player |
| **🗄️ SQLite Database** | Persistent storage with ratings, play history, playlists |
| **🎹 Audio Analysis** | BPM detection, musical key detection, waveform generation |
| **🔊 Audio Processing** | Normalize volume, convert formats (MP3/FLAC/WAV) |
| **🖼️ Cover Art Manager** | Download and organize album artwork |
| **🔄 Duplicate Detection** | Find duplicates by title, audio fingerprint, or hash |
| **⭐ Rating System** | Rate songs 1-5 stars with persistent storage |
| **📜 Listening History** | Track play counts and recently played |
| **⚙️ YAML Configuration** | Centralized config file for all settings |
| **📤 Spotify Export** | Export to Spotify-compatible CSV format |

### Comparison with Competitors

| Feature | Suno Extractor Pro | Malith-Rukshan/Suno-API | GwyrddGlas/Suno-Downloader |
|---------|-------------------|------------------------|---------------------------|
| Extract from Library | ✅ Full | ❌ | ❌ |
| Audio Download | ✅ | ✅ | ✅ |
| ID3 Metadata | ✅ | ❌ | ❌ |
| Cover Art | ✅ Embed + Separate | ❌ | ❌ |
| Music Player | ✅ Terminal + Web | ❌ | ❌ |
| Web Dashboard | ✅ Flask UI | ❌ | ❌ |
| Database | ✅ SQLite | ❌ | ❌ |
| BPM/Key Detection | ✅ librosa | ❌ | ❌ |
| Audio Normalization | ✅ pydub | ❌ | ❌ |
| Duplicate Detection | ✅ | ❌ | ❌ |
| Rating System | ✅ | ❌ | ❌ |
| Playlist Export | ✅ M3U | ❌ | ❌ |
| Spotify Export | ✅ CSV | ❌ | ❌ |
| CLI Interface | ✅ Rich | ✅ Basic | ✅ Basic |
| Export Formats | MD/JSON/CSV | JSON | - |

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/suno-extractor.git
cd suno-extractor

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

#### 1. Extract Songs from Suno

```bash
# Start Chrome with debugging enabled
chrome.exe --remote-debugging-port=9222

# Run extraction
python suno_cli.py extract --browser chrome --port 9222
```

#### 2. Download Audio Files

```bash
python suno_cli.py download --json-file suno_songs/suno_liked_songs_20251031.json
```

#### 3. View Statistics

```bash
python suno_cli.py stats
```

#### 4. Search Your Collection

```bash
python suno_cli.py search "electronic"
```

#### 5. Play Music

```bash
python suno_player.py --dir suno_downloads
```

## 📖 Module Reference

### `suno_extractor.py` - Web Scraper

The core extraction engine that connects to your browser and extracts song data.

```python
from suno_extractor import SunoExtractor

extractor = SunoExtractor(output_dir="suno_songs", browser="chrome")
extractor.connect_to_existing_browser(debug_port=9222)
output_files = extractor.run_extraction(
    extract_details=True,
    save_formats=['md', 'json', 'csv'],
    tabs=['creations', 'likes']
)
```

### `suno_downloader.py` - Audio Downloader

Downloads audio files with automatic ID3 tagging.

```python
from suno_downloader import SunoDownloader, CollectionAnalyzer

# Download all songs
downloader = SunoDownloader("suno_downloads")
results = downloader.download_from_json("suno_songs/collection.json")

# Analyze collection
analyzer = CollectionAnalyzer("suno_songs/collection.json")
stats = analyzer.get_statistics()
print(f"Total songs: {stats['total_songs']}")
print(f"Total duration: {stats['total_duration_formatted']}")
```

### `suno_player.py` - Music Player

Terminal-based music player with full controls.

```python
from suno_player import SunoPlayer, PlayerUI

player = SunoPlayer("suno_downloads")
player.load_playlist_from_dir()
player.play(0)  # Play first song

# Or run interactive UI
ui = PlayerUI(player)
ui.run()
```

### `suno_cli.py` - Command Line Interface

Full-featured CLI with all commands.

```bash
# Available commands
python suno_cli.py extract     # Extract from Suno
python suno_cli.py download    # Download audio files
python suno_cli.py stats       # Show statistics
python suno_cli.py search      # Search collection
python suno_cli.py playlist    # Create M3U playlist
python suno_cli.py list        # List all songs
python suno_cli.py interactive # Interactive menu
```

## 📁 Project Structure

```
suno-extractor/
├── suno_extractor.py      # Core web scraper
├── suno_downloader.py     # Audio downloader & ID3 tagger
├── suno_player.py         # Terminal music player
├── suno_cli.py            # Rich CLI interface
├── suno_core.py           # Config & SQLite database
├── suno_audio.py          # BPM/key detection, waveforms, normalization
├── suno_web.py            # Flask web dashboard
├── config.yaml            # Configuration file
├── requirements.txt       # Dependencies
├── README.md              # This file
├── suno_library.db        # SQLite database
├── suno_songs/            # Extracted metadata (JSON, CSV, MD)
├── suno_downloads/        # Downloaded audio files
├── suno_covers/           # Cover art images
├── suno_waveforms/        # Generated waveform images
└── suno_playlists/        # Generated playlists
```

## 🌐 Web Dashboard

Start the beautiful web interface:

```bash
python suno_web.py --port 5000
```

Open http://localhost:5000 in your browser for:
- Visual library browsing with cover art
- Built-in audio player with progress bar
- Star ratings (1-5)
- Search and filter
- Statistics dashboard
- Import/Export tools
- Spotify CSV export

## 🔧 Configuration

### Browser Setup (Chrome)

```bash
# Windows
chrome.exe --remote-debugging-port=9222

# Mac
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222
```

### Environment Variables (Optional)

```bash
export SUNO_OUTPUT_DIR="suno_songs"
export SUNO_DOWNLOAD_DIR="suno_downloads"
export SUNO_BROWSER="chrome"
export SUNO_DEBUG_PORT="9222"
```

## 📊 Output Formats

### JSON Export
```json
{
  "metadata": {
    "extracted_at": "2025-11-27T00:00:00",
    "total_songs": 46
  },
  "songs": [
    {
      "title": "My Song",
      "artist": "Suno AI",
      "duration": "3:24",
      "lyrics": "...",
      "tags": ["electronic", "v5"],
      "url": "https://suno.com/song/..."
    }
  ]
}
```

### M3U Playlist
```m3u
#EXTM3U
#EXTINF:204,Suno AI - My Song
C:\suno_downloads\My Song.mp3
```

## 🎮 Player Controls

| Key | Action |
|-----|--------|
| `Space` | Play/Pause |
| `N` | Next track |
| `P` | Previous track |
| `+/-` | Volume up/down |
| `S` | Toggle shuffle |
| `R` | Toggle repeat |
| `L` | Show playlist |
| `Q` | Quit |

## 🛠️ Troubleshooting

### Chrome Connection Failed
```
Make sure Chrome is running with: chrome.exe --remote-debugging-port=9222
```

### No Songs Extracted
- Ensure you're logged into Suno
- Navigate to your library page before extraction
- Check if the page has fully loaded

### Download Failed
- Some songs may not have audio files available
- Check your internet connection
- Verify the song URL is accessible

## 📝 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

Contributions welcome! Please read the contributing guidelines first.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 🎹 Audio Analysis

Analyze your music collection for BPM, musical key, and more:

```bash
# Analyze a single file
python suno_audio.py analyze path/to/song.mp3

# Generate waveform image
python suno_audio.py waveform path/to/song.mp3

# Batch analyze all downloaded songs
python suno_audio.py batch-analyze suno_downloads/

# Normalize audio volume
python suno_audio.py normalize path/to/song.mp3

# Convert format
python suno_audio.py convert path/to/song.mp3 flac
```

**Note:** Audio analysis requires optional dependencies:
```bash
pip install librosa numpy matplotlib pydub
```

## 🙏 Acknowledgments

- [Suno AI](https://suno.com) - AI music generation platform
- [Selenium](https://selenium.dev) - Browser automation
- [Flask](https://flask.palletsprojects.com) - Web framework
- [Rich](https://rich.readthedocs.io) - Terminal formatting
- [Mutagen](https://mutagen.readthedocs.io) - Audio metadata
- [Pygame](https://pygame.org) - Audio playback
- [librosa](https://librosa.org) - Audio analysis
- [pydub](https://github.com/jiaaro/pydub) - Audio processing
