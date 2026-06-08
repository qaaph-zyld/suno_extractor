#!/usr/bin/env python3
import io, sys, sqlite3, subprocess
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

AUDIO_DIR = Path("suno_library/audio")

def convert_mp3_to_wav(mp3_path):
    wav_path = mp3_path.with_suffix(".wav")
    if wav_path.exists():
        print("  WAV already exists, skipping: %s" % wav_path.name)
        return wav_path
    cmd = [
        "ffmpeg", "-y", "-i", str(mp3_path), "-acodec", "pcm_s16le", "-ar", "44100",
        "-ac", "2", str(wav_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and wav_path.exists():
            return wav_path
        else:
            print("  FFmpeg failed for %s: %s" % (mp3_path.name, result.stderr[:200]))
            return None
    except Exception as e:
        print("  Error converting %s: %s" % (mp3_path.name, e))
        return None

def update_db(conn, song_id, wav_path):
    c = conn.cursor()
    c.execute("UPDATE songs SET local_audio_path = ? WHERE id = ?", (str(wav_path), song_id))

def extract_song_id_from_filename(filename):
    # Try to extract song ID from filename like Title_abc12345.mp3
    # The suno_downloader uses {safe_title}_{song_id[:8]}.{ext}
    stem = filename.stem
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and len(parts[1]) == 8:
        return parts[1]
    return None

def main():
    mp3_files = sorted(AUDIO_DIR.glob("*.mp3"))
    print("Found %d MP3 files to convert" % len(mp3_files))
    converted = 0
    failed = 0
    skipped = 0

    conn = sqlite3.connect("suno_library.db", timeout=30.0)
    c = conn.cursor()

    for i, mp3_path in enumerate(mp3_files, 1):
        print("[%d/%d] %s..." % (i, len(mp3_files), mp3_path.name))
        wav_path = convert_mp3_to_wav(mp3_path)
        if wav_path:
            if wav_path.exists() and mp3_path.exists():
                # Find song_id in DB by matching the old MP3 path
                c.execute("SELECT id FROM songs WHERE local_audio_path LIKE ?", ("%" + mp3_path.name + "%",))
                row = c.fetchone()
                if row:
                    update_db(conn, row[0], wav_path)
                    print("  Updated DB for %s" % row[0])
                # Delete original MP3
                try:
                    mp3_path.unlink()
                    print("  Deleted original MP3")
                    converted += 1
                except Exception as e:
                    print("  Could not delete MP3: %s" % e)
            else:
                skipped += 1
        else:
            failed += 1

    conn.commit()
    conn.close()
    print("\nDone: %d converted, %d failed, %d skipped" % (converted, failed, skipped))

if __name__ == "__main__":
    main()
