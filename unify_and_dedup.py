#!/usr/bin/env python3
"""
Move all files from suno_downloads/ into suno_library/audio/.
Since downloads/ files have no song ID suffixes, they won't collide
with audio/ files that do have suffixes. Then rename everything
consistently and deduplicate by song ID.
"""

import os
import shutil
import re
import sqlite3
from pathlib import Path
from collections import defaultdict

AUDIO_DIR = Path("suno_library/audio")
DOWNLOADS_DIR = Path("suno_downloads")

def safe_filename(title: str, max_len: int = 200) -> str:
    safe = re.sub(r'[<>:"/\\|?*]', '', str(title))
    safe = safe.strip('. ')
    return safe[:max_len] if safe else "untitled"

def main():
    print("=== Step 1: Move downloads/ files to audio/ ===")
    
    moved = 0
    skipped = 0
    
    for f in DOWNLOADS_DIR.iterdir():
        if f.is_file():
            dest = AUDIO_DIR / f.name
            if dest.exists():
                # If a file with the same name exists, skip (don't overwrite)
                skipped += 1
            else:
                shutil.move(str(f), str(dest))
                moved += 1
    
    print(f"Moved: {moved}, Skipped (already exists): {skipped}")
    
    # Now try to match all audio files to database songs and rename consistently
    print("\n=== Step 2: Match files to database and rename consistently ===")
    
    conn = sqlite3.connect('suno_library.db')
    c = conn.cursor()
    c.execute('SELECT id, title FROM songs')
    songs = c.fetchall()
    conn.close()
    
    # Build title -> song_id mapping
    title_to_id = {}
    for song_id, title in songs:
        sf = safe_filename(title)
        title_to_id[sf] = song_id
    
    # Scan audio/ for files that don't have song ID suffix
    renamed = 0
    for f in AUDIO_DIR.iterdir():
        if f.is_file():
            stem = f.stem
            # Check if already has _songid pattern
            if re.search(r'_([0-9a-fA-F]{8})$', stem):
                continue
            
            # Try to match by title
            if stem in title_to_id:
                song_id = title_to_id[stem]
                new_name = f"{stem}_{song_id[:8]}{f.suffix}"
                new_path = AUDIO_DIR / new_name
                if not new_path.exists():
                    try:
                        f.rename(new_path)
                        renamed += 1
                    except (PermissionError, OSError) as e:
                        print(f"  Warning: could not rename {f.name}: {e}")
    
    print(f"Renamed to include song ID: {renamed}")
    
    print("\n=== Step 3: Deduplicate by song ID ===")
    
    # Group files by song ID
    id_to_files = defaultdict(list)
    for f in AUDIO_DIR.iterdir():
        if f.is_file():
            match = re.search(r'_([0-9a-fA-F]{8})$', f.stem)
            if match:
                song_id = match.group(1).lower()
                id_to_files[song_id].append(f)
    
    duplicates_found = 0
    deleted = 0
    for song_id, files in id_to_files.items():
        if len(files) > 1:
            duplicates_found += 1
            # Keep the largest file, delete the rest
            files_sorted = sorted(files, key=lambda f: f.stat().st_size, reverse=True)
            keep = files_sorted[0]
            for f in files_sorted[1:]:
                try:
                    f.unlink()
                    deleted += 1
                except (PermissionError, OSError) as e:
                    print(f"  Warning: could not delete {f.name}: {e}")
    
    print(f"Duplicate song IDs found: {duplicates_found}")
    print(f"Extra files deleted: {deleted}")
    
    final_count = sum(1 for _ in AUDIO_DIR.iterdir() if _.is_file())
    print(f"\nFinal audio/ file count: {final_count}")

if __name__ == "__main__":
    main()
