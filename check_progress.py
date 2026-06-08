#!/usr/bin/env python3
import json, sqlite3
from pathlib import Path

# Check progress file
if Path("metadata_progress.json").exists():
    with open("metadata_progress.json", "r", encoding="utf-8") as f:
        done = set(json.load(f))
    print("Progress file entries: %d" % len(done))
else:
    print("No progress file")
    done = set()

# Check DB state
conn = sqlite3.connect("suno_library.db")
c = conn.cursor()
c.execute("SELECT id, title, lyrics, description FROM songs WHERE is_liked=1")
rows = c.fetchall()
conn.close()

missing_lyrics = 0
missing_desc = 0
missing_both = 0
in_progress = 0
for song_id, title, lyrics, description in rows:
    if not lyrics or len(lyrics) == 0:
        missing_lyrics += 1
    if not description or len(description) == 0:
        missing_desc += 1
    if (not lyrics or len(lyrics) == 0) and (not description or len(description) == 0):
        missing_both += 1
    if song_id in done and (not lyrics or len(lyrics) == 0):
        in_progress += 1

print("Liked songs: %d" % len(rows))
print("Missing lyrics: %d" % missing_lyrics)
print("Missing description: %d" % missing_desc)
print("Missing both: %d" % missing_both)
print("In progress file but still missing lyrics: %d" % in_progress)
