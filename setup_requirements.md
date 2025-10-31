# Suno Extractor - Existing Browser Setup Guide

## Quick Start (3 Steps)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
# or on Windows PowerShell
py -m pip install -r requirements.txt
```

### 2. Start Browser with Remote Debugging

**Chrome (recommended):**
```powershell
# Windows (PowerShell)
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$env:TEMP\chrome_debug"
```

If you want to reuse your existing Chrome profile (no re-login), close all Chrome windows first, then:

```powershell
$profile = "$env:LOCALAPPDATA\Google\Chrome\User Data"
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$profile" https://suno.com/library
```

```bash
# Linux
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_debug

# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_debug
```

> Note: Attaching to an already running Firefox session via Selenium is not reliably supported. Use Chrome with `--remote-debugging-port=9222` for this workflow.

### 3. Login & Run Script

1. **In the browser**: Navigate to https://suno.com and log in
2. **Leave browser open** and logged in
3. **Run extraction**:

```bash
python suno_extractor.py
```

Done! The script connects to your open browser and extracts everything automatically.

---

## Detailed Setup

### Install WebDriver

No manual driver install is required for Chrome. The script uses `webdriver-manager` to automatically download and manage the correct ChromeDriver version.

Optional manual installs (if you prefer):

**Chrome (chromedriver):**
```bash
# Ubuntu/Debian
sudo apt install chromium-chromedriver

# macOS
brew install chromedriver

# Manual download: https://chromedriver.chromium.org/downloads
```

### Verify Installation

```bash
# Check geckodriver
geckodriver --version

# Check chromedriver
chromedriver --version

# Test selenium
python3 -c "from selenium import webdriver; print('✓ Selenium ready')"
```

---

## Configuration Options

Edit the `main()` function in `suno_extractor.py`:

```python
# Browser selection
BROWSER = "chrome"  # or "firefox"

# Debug port (must match browser launch command)
DEBUG_PORT = 9222  # Chrome default: 9222

# Output directory
OUTPUT_DIR = "suno_songs"

# Extract full details (visits each song page)
EXTRACT_DETAILS = True  # False for faster, less detailed extraction

# Export formats
SAVE_FORMATS = ['md', 'json', 'csv']  # Choose any combination
```

---

## Usage Scenarios

### Scenario 1: Quick Extraction (Already Logged In)

```bash
# 1. Browser already open with Suno logged in
# 2. Just run:
python3 suno_extractor.py
```

### Scenario 2: Automated Daily Backup

Create `extract_daily.sh`:

```bash
#!/bin/bash

# Start Chrome with debugging
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_debug &
CHROME_PID=$!

# Wait for browser to start
sleep 5

# Run extraction
python3 suno_extractor.py

# Optional: Close Chrome
# kill $CHROME_PID
```

Schedule with cron:
```bash
crontab -e
# Add: 0 2 * * * /path/to/extract_daily.sh
```

### Scenario 3: Extract Without Full Details (Fast)

```python
# In suno_extractor.py, set:
EXTRACT_DETAILS = False
```

This skips visiting individual song pages, extracting only data visible on the library page. **~10x faster** for large collections.

### Scenario 4: Multiple Export Formats

```python
# Export to all formats
SAVE_FORMATS = ['md', 'json', 'csv']

# Markdown only (human-readable)
SAVE_FORMATS = ['md']

# JSON only (programmatic access)
SAVE_FORMATS = ['json']

# CSV only (spreadsheet analysis)
SAVE_FORMATS = ['csv']
```

---

## Output Format Details

### Markdown (.md)
```markdown
# 🎵 Suno Liked Songs

**Extracted:** 2025-10-31 15:30:00
**Total Songs:** 42

---

## 📑 Table of Contents
1. [Electronic Dreams](#electronic-dreams)
2. [Neon Nights](#neon-nights)
...

---

## 1. Electronic Dreams

| Attribute | Value |
|-----------|-------|
| **Artist** | AI Creator |
| **Duration** | 3:24 |
| **URL** | [https://suno.com/song/...](https://suno.com/song/...) |

**Tags:** `electronic` • `synthwave` • `ambient`

### 📝 Description
An atmospheric journey through digital soundscapes...

### 🎤 Lyrics
```
[Verse 1]
In the circuit of the night...
```
```

### JSON (.json)
```json
{
  "metadata": {
    "extracted_at": "2025-10-31T15:30:00",
    "total_songs": 42,
    "extractor_version": "2.0"
  },
  "songs": [
    {
      "index": 1,
      "title": "Electronic Dreams",
      "artist": "AI Creator",
      "duration": "3:24",
      "tags": ["electronic", "synthwave"],
      "lyrics": "[Verse 1]\nIn the circuit...",
      "url": "https://suno.com/song/..."
    }
  ]
}
```

### CSV (.csv)
```csv
index,title,artist,duration,plays,likes,created_at,tags,description,lyrics,url
1,"Electronic Dreams","AI Creator","3:24","1.2K","345","2 days ago","electronic, synthwave","Description...","[Verse 1]...","https://..."
```

---

## Troubleshooting

### Issue: "Failed to connect to browser"

**Solution:**
```powershell
# 1. Check if Chrome is running (Windows)
Get-Process chrome

# 2. Verify script port matches browser launch
# Chrome: --remote-debugging-port=9222

# 3. Close all Chrome windows and restart with the flag above
```

### Issue: "No songs extracted"

**Causes & Solutions:**

1. **Not on liked songs page:**
   ```python
   # Manually navigate to: https://suno.com/library → Liked tab
   # Then re-run script
   ```

2. **Page structure changed:**
   ```bash
   # Enable debug logging
   # In suno_extractor.py, change:
   logging.basicConfig(level=logging.DEBUG, ...)
   ```

3. **Need more scroll time:**
   ```python
   # In scroll_to_load_all(), increase:
   scroll_pause: float = 3.0  # from 2.0
   ```

### Issue: "Connection refused" (Chrome)

**Solution:**
```bash
# Ensure user-data-dir is writable and unique
# Linux/macOS:
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_debug_$(date +%s)

# Windows (PowerShell):
"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$env:TEMP\\chrome_debug_$(Get-Random)"
```

### Issue: Missing lyrics or descriptions

**Cause:** `EXTRACT_DETAILS = False`

**Solution:**
```python
# Set to True in configuration
EXTRACT_DETAILS = True
```

This makes the script visit each song's individual page to extract full content.

---

## Advanced Customization

### Custom Selectors

If Suno updates their HTML structure, update selectors in `_parse_song_element()`:

```python
def _parse_song_element(self, element, idx: int):
    # Update these regex patterns to match new class names
    title_elem = element.find(class_=re.compile(r'your-new-title-class', re.I))
    artist_elem = element.find(class_=re.compile(r'your-new-artist-class', re.I))
    # ...
```

### Adjust Scrolling Behavior

```python
def scroll_to_load_all(self, scroll_pause: float = 2.0, max_scrolls: int = 150):
    # Increase for large collections
    max_scrolls: int = 300
    
    # Increase pause for slow connections
    scroll_pause: float = 3.0
```

### Filter Songs During Extraction

```python
def extract_all_songs(self) -> List[Dict]:
    songs = []
    # ... existing extraction code ...
    
    # Filter: only songs with lyrics
    songs = [s for s in songs if s.get('lyrics')]
    
    # Filter: only songs with specific tags
    songs = [s for s in songs if 'electronic' in s.get('tags', [])]
    
    return songs
```

### Add Custom Export Format

```python
def save_to_html(self, songs: List[Dict], filename: str = None) -> Path:
    """Export as HTML gallery"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"suno_gallery_{timestamp}.html"
    
    filepath = self.output_dir / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('<!DOCTYPE html><html><head><title>Suno Songs</title></head><body>')
        for song in songs:
            f.write(f'<div class="song">')
            f.write(f'<h2>{song["title"]}</h2>')
            if song.get('image_url'):
                f.write(f'<img src="{song["image_url"]}" alt="{song["title"]}">')
            f.write(f'<p>{song["description"]}</p>')
            f.write(f'</div>')
        f.write('</body></html>')
    
    return filepath

# Add to save_formats
SAVE_FORMATS = ['md', 'json', 'csv', 'html']
```

---

## Performance Optimization

### Large Collections (500+ songs)

```python
# 1. Disable detailed extraction for initial run
EXTRACT_DETAILS = False

# 2. Increase scroll batch size
def scroll_to_load_all(self, scroll_pause: float = 1.0, max_scrolls: int = 300):
    # Reduced pause, increased max scrolls

# 3. Run in headless Chrome (faster rendering)
# Use Chrome instead of Firefox
BROWSER = "chrome"
```

### Network Optimization

```python
# In connect_to_existing_browser(), add options:
if self.browser_type == "chrome":
    options.add_argument('--disable-images')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-gpu')
```

---

## Batch Processing

### Extract Multiple Users' Libraries

```python
def extract_user_library(username: str):
    extractor = SunoExtractor(output_dir=f"suno_songs/{username}")
    extractor.connect_to_existing_browser()
    
    # Navigate to user's profile
    extractor.driver.get(f"https://suno.com/@{username}")
    # ... extraction logic ...

# Usage
for user in ['user1', 'user2', 'user3']:
    extract_user_library(user)
```

### Incremental Updates

```python
# Load previous extraction
import json

previous_file = "suno_songs/suno_liked_songs_20251030_120000.json"
with open(previous_file) as f:
    previous_data = json.load(f)
    previous_urls = {song['url'] for song in previous_data['songs']}

# Extract only new songs
new_songs = [s for s in songs if s['url'] not in previous_urls]
```

---

## Security & Privacy

### Never Commit Credentials

```python
# Use environment variables
import os

EMAIL = os.getenv('SUNO_EMAIL')
PASSWORD = os.getenv('SUNO_PASSWORD')

# Set in terminal:
# export SUNO_EMAIL="your@email.com"
# export SUNO_PASSWORD="yourpassword"
```

### Rate Limiting

```python
def extract_detailed_info(self, songs: List[Dict], delay: float = 2.0):
    # Increase delay to be respectful to servers
    delay: float = 3.0
    
    # Add random jitter
    import random
    time.sleep(delay + random.uniform(0, 1))
```

---

## Integration Examples

### Export to Spotify Playlist (Concept)

```python
def export_to_spotify_format(songs: List[Dict]) -> List[str]:
    """Convert to Spotify search queries"""
    queries = []
    for song in songs:
        # Format: "title artist"
        query = f"{song['title']} {song['artist']}"
        queries.append(query)
    return queries

# Save search queries
with open('spotify_searches.txt', 'w') as f:
    for query in export_to_spotify_format(songs):
        f.write(f"{query}\n")
```

### Analyze Tags with Pandas

```python
import pandas as pd
import json

# Load JSON
with open('suno_liked_songs.json') as f:
    data = json.load(f)

# Create DataFrame
df = pd.DataFrame(data['songs'])

# Explode tags
df_tags = df.explode('tags')

# Most common tags
print(df_tags['tags'].value_counts().head(10))

# Songs by tag
electronic_songs = df[df['tags'].apply(lambda x: 'electronic' in x)]
```

---

## Logging & Monitoring

### Enable Detailed Logging

```python
# In suno_extractor.py, modify logging config:
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('suno_extractor_debug.log'),
        logging.StreamHandler()
    ]
)
```

### Progress Monitoring

```python
def extract_detailed_info(self, songs: List[Dict], delay: float = 1.5):
    from tqdm import tqdm  # pip install tqdm
    
    for song in tqdm(songs, desc="Extracting details"):
        # ... extraction code ...
```

---

## Requirements File

Create `requirements.txt`:

```txt
# Core dependencies
selenium==4.15.2
beautifulsoup4==4.12.2
lxml==4.9.3
webdriver-manager==4.0.2

# Optional: Progress bars
tqdm==4.66.1

# Optional: Data analysis
pandas==2.1.3
```

Install all:
```bash
pip install -r requirements.txt
```

---

## Complete Workflow Example

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start Chrome with debugging
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_debug &

# 3. Login to Suno (in browser)
# Navigate to: https://suno.com
# Click "Sign In"
# Complete login

# 4. Navigate to liked songs (in browser)
# Click "Library" → "Liked"

# 5. Run extraction
python3 suno_extractor.py

# 6. Check output
ls -lh suno_songs/
```

Output:
```
✓ EXTRACTION COMPLETE
✓ Total songs: 156
✓ MARKDOWN: suno_songs/suno_liked_songs_20251031_153000.md
✓ JSON: suno_songs/suno_liked_songs_20251031_153000.json
✓ CSV: suno_songs/suno_liked_songs_20251031_153000.csv
```

---

## FAQ

**Q: Can I run this on a server without a display?**

A: Yes, use Xvfb (virtual framebuffer):
```bash
sudo apt install xvfb
xvfb-run --server-args="-screen 0 1920x1080x24" python3 suno_extractor.py
```

**Q: How long does extraction take?**

A: 
- Without details: ~2-5 seconds per song
- With details: ~3-5 seconds per song
- 100 songs: ~5-8 minutes
- 500 songs: ~25-40 minutes

**Q: Can I extract playlists or other users' songs?**

A: Yes, modify the `navigate_to_liked_songs()` method to navigate to any URL:
```python
self.driver.get("https://suno.com/@username")
self.driver.get("https://suno.com/playlist/xyz")
```

**Q: Does this violate Suno's Terms of Service?**

A: This tool is for personal backup/archival purposes. Review Suno's TOS and use responsibly.

---

## License

Open source, personal use only. Respect Suno's content and Terms of Service.