#!/usr/bin/env python3
"""
Rebuild database local_audio_path mappings and generate clean missing list.
"""

import os
import re
import json
import sqlite3
from pathlib import Path
from collections import defaultdict

AUDIO_DIR = Path("suno_library/audio")

def safe_filename(title: str, max_len: int = 200) -> str:
    safe = re.sub(r'[<>:"/\\|?*]', '', str(title))
    safe = safe.strip('. ')
    return safe[:max_len] if safe else "untitled"

def main():
    print("=== Step 1: Scan audio files and build song_id -> file mapping ===")
    
    # Group files by song ID (from filename suffix _songid)
    id_to_files = defaultdict(list)
    unmatched = []
    
    for f in AUDIO_DIR.iterdir():
        if f.is_file():
            match = re.search(r'_([0-9a-fA-F]{8})$', f.stem)
            if match:
                song_id = match.group(1).lower()
                id_to_files[song_id].append(f)
            else:
                unmatched.append(f.name)
    
    print(f"Files with song ID: {len(id_to_files)}")
    print(f"Files without song ID: {len(unmatched)}")
    
    print("\n=== Step 2: Connect to database and update paths ===")
    
    conn = sqlite3.connect('suno_library.db')
    c = conn.cursor()
    
    # Get all song IDs from database
    c.execute('SELECT id FROM songs')
    db_ids = {row[0] for row in c.fetchall()}
    print(f"Total songs in database: {len(db_ids)}")
    
    # For each file with song ID, update the database
    updated = 0
    not_found = 0
    multiple = 0
    
    for song_id in id_to_files:
        files = id_to_files[song_id]
        # If multiple files for same ID, pick the largest one
        if len(files) > 1:
            multiple += 1
            best = max(files, key=lambda f: f.stat().st_size)
        else:
            best = files[0]
        
        # Find full song_id in database
        full_id = None
        for db_id in db_ids:
            if db_id.startswith(song_id):
                full_id = db_id
                break
        
        if full_id:
            rel_path = str(best)
            c.execute(
                'UPDATE songs SET local_audio_path = ? WHERE id = ?',
                (rel_path, full_id)
            )
            updated += 1
        else:
            not_found += 1
    
    conn.commit()
    print(f"Updated local_audio_path: {updated}")
    print(f"Files not matched to DB: {not_found}")
    print(f"Multiple files per ID (kept largest): {multiple}")
    
    # Also check how many DB songs have paths now
    c.execute("SELECT COUNT(*) FROM songs WHERE local_audio_path IS NOT NULL AND local_audio_path != ''")
    with_audio = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM songs')
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM songs WHERE is_liked = 1")
    liked = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM songs WHERE is_liked = 1 AND (local_audio_path IS NOT NULL AND local_audio_path != '')")
    liked_with_audio = c.fetchone()[0]
    
    print(f"\n=== Current State ===")
    print(f"Total DB songs: {total}")
    print(f"Songs with audio: {with_audio}")
    print(f"Liked songs: {liked}")
    print(f"Liked with audio: {liked_with_audio}")
    print(f"Liked missing audio: {liked - liked_with_audio}")
    
    print("\n=== Step 3: Generate clean missing list for LIKED songs ===")
    
    c.execute('''
        SELECT id, title, url 
        FROM songs 
        WHERE is_liked = 1 
        AND (local_audio_path IS NULL OR local_audio_path = '')
    ''')
    missing = c.fetchall()
    
    missing_list = []
    for song_id, title, url in missing:
        sf = safe_filename(title)
        missing_list.append({
            'id': song_id,
            'title': title,
            'safe_title': sf,
            'url': url
        })
    
    with open('missing_liked_songs.json', 'w', encoding='utf-8') as f:
        json.dump(missing_list, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(missing_list)} missing liked songs to missing_liked_songs.json")
    
    conn.close()

if __name__ == "__main__":
    main()
