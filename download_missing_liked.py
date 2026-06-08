#!/usr/bin/env python3
import io, sys, json, sqlite3, time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))
from suno_downloader import SunoDownloader

AUDIO_DIR = Path("suno_library/audio")
MISSING_FILE = "missing_liked_songs.json"
PROGRESS_FILE = Path("download_progress.json")

def load_missing():
    with open(MISSING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_progress(done_ids):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(done_ids), f, indent=2)

def update_db(song_id, filepath):
    conn = sqlite3.connect("suno_library.db")
    c = conn.cursor()
    c.execute("UPDATE songs SET local_audio_path = ? WHERE id = ?", (str(filepath), song_id))
    conn.commit()
    conn.close()

def main():
    missing = load_missing()
    done = load_progress()
    remaining = [s for s in missing if s["id"] not in done]
    print("Total missing: %d, Done: %d, Remaining: %d" % (len(missing), len(done), len(remaining)))
    if not remaining:
        print("Nothing to download!")
        return
    downloader = SunoDownloader(str(AUDIO_DIR))
    for i, song in enumerate(remaining, 1):
        title = song.get("title", "untitled")
        song_id = song["id"]
        print("[%d/%d] Downloading: %s..." % (i, len(remaining), title[:50]))
        try:
            result = downloader.download_audio(song, format="wav")
            if result:
                done.add(song_id)
                save_progress(done)
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
