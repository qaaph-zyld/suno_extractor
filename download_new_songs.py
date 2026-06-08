#!/usr/bin/env python3
import io, sys, json, sqlite3, time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))
from suno_downloader import SunoDownloader

AUDIO_DIR = Path("suno_library/audio")
MISSING_FILE = "missing_new_songs.json"

def load_missing():
    with open(MISSING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def update_db(song_id, filepath):
    conn = sqlite3.connect("suno_library.db")
    c = conn.cursor()
    c.execute("UPDATE songs SET local_audio_path = ? WHERE id = ?", (str(filepath), song_id))
    conn.commit()
    conn.close()

def main():
    missing = load_missing()
    print("Downloading %d new songs..." % len(missing))
    if not missing:
        print("Nothing to download!")
        return
    downloader = SunoDownloader(str(AUDIO_DIR))
    for i, song in enumerate(missing, 1):
        title = song.get("title", "untitled")
        song_id = song["id"]
        print("[%d/%d] Downloading: %s..." % (i, len(missing), title[:50]))
        try:
            result = downloader.download_audio(song, format="wav")
            if result:
                update_db(song_id, result)
                print("  OK: %s" % result.name)
            else:
                print("  FAILED: no result")
        except Exception as e:
            print("  ERROR: %s" % e)
        time.sleep(0.5)
    print("Batch complete.")

if __name__ == "__main__":
    main()
