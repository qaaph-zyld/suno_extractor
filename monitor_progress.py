#!/usr/bin/env python3
"""Quick progress monitor for lyrics extraction."""
import json
import sqlite3
from pathlib import Path

def main():
    # Progress file
    progress_count = 0
    if Path("metadata_progress.json").exists():
        with open("metadata_progress.json") as f:
            progress_count = len(set(json.load(f)))
    
    # Database stats
    conn = sqlite3.connect("suno_library.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM songs WHERE is_liked=1")
    liked = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM songs WHERE is_liked=1 AND lyrics IS NOT NULL AND length(lyrics)>0")
    with_lyrics = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM songs WHERE is_liked=1 AND (lyrics IS NULL OR lyrics='')")
    missing = c.fetchone()[0]
    conn.close()
    
    print("=" * 50)
    print("Suno Lyrics Extraction Progress")
    print("=" * 50)
    print(f"Liked songs in DB:     {liked}")
    print(f"Processed (progress):  {progress_count}")
    print(f"With lyrics:           {with_lyrics}")
    print(f"Missing lyrics:        {missing}")
    print(f"Completion:            {with_lyrics/liked*100:.1f}%")
    print("=" * 50)
    
    if progress_count > 0:
        # Estimate completion time
        remaining = missing
        rate = 400  # songs per hour (observed average)
        hours = remaining / rate
        print(f"Estimated time remaining: ~{hours:.1f} hours at {rate}/hr")

if __name__ == "__main__":
    main()
