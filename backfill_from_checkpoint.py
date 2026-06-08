#!/usr/bin/env python3
import json, sqlite3
from pathlib import Path

def main():
    checkpoint = "suno_songs/suno_liked_phase2_details_2100_20260526_001659.json"
    print("Loading checkpoint: %s" % checkpoint)
    with open(checkpoint, "r", encoding="utf-8") as f:
        data = json.load(f)
    songs = data.get("songs", [])
    print("Loaded %d songs from checkpoint" % len(songs))

    # Build lookup by ID
    by_id = {}
    for s in songs:
        sid = s.get("id")
        if sid:
            by_id[sid] = s

    conn = sqlite3.connect("suno_library.db")
    c = conn.cursor()
    c.execute("SELECT id, lyrics, description FROM songs WHERE is_liked=1")
    rows = c.fetchall()

    updated = 0
    for song_id, old_lyrics, old_desc in rows:
        song = by_id.get(song_id)
        if not song:
            continue
        new_lyrics = old_lyrics
        new_desc = old_desc
        changed = False

        cp_lyrics = song.get("lyrics", "")
        cp_desc = song.get("description", "")

        if (not old_lyrics or len(old_lyrics) == 0) and cp_lyrics and len(cp_lyrics) > 0:
            new_lyrics = cp_lyrics
            changed = True
        if (not old_desc or len(old_desc) == 0) and cp_desc and len(cp_desc) > 0:
            new_desc = cp_desc
            changed = True

        if changed:
            c.execute("UPDATE songs SET lyrics = ?, description = ? WHERE id = ?",
                      (new_lyrics, new_desc, song_id))
            updated += 1

    conn.commit()
    conn.close()
    print("Updated %d songs from checkpoint" % updated)

if __name__ == "__main__":
    main()
