import json, sqlite3, os
from pathlib import Path

# Load extracted data
checkpoint_file = 'suno_songs/suno_liked_songs_20260608_232558.json'
with open(checkpoint_file, encoding='utf-8') as f:
    data = json.load(f)
extracted_songs = data['songs']

print(f"Loaded {len(extracted_songs)} songs from checkpoint")

# Connect to database
db_path = 'suno_library.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Create table if not exists
c.execute('''
CREATE TABLE IF NOT EXISTS songs (
    id TEXT PRIMARY KEY,
    title TEXT,
    artist TEXT,
    description TEXT,
    tags TEXT,
    lyrics TEXT,
    plays INTEGER,
    url TEXT,
    local_audio_path TEXT,
    local_lyrics_path TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Get existing song IDs
c.execute('SELECT id FROM songs')
existing_ids = {row[0] for row in c.fetchall()}
print(f"Found {len(existing_ids)} existing songs in database")

# Merge: insert new songs, update existing
new_count = 0
updated_count = 0

for song in extracted_songs:
    song_id = song.get('id')
    if not song_id:
        continue
    
    # Check if song exists
    if song_id in existing_ids:
        # Update existing
        c.execute('''
        UPDATE songs SET
            title = ?, artist = ?, description = ?, lyrics = ?,
            url = ?, image_url = ?, extracted_at = CURRENT_TIMESTAMP
        WHERE id = ?
        ''', (
            song.get('title', ''),
            song.get('artist', ''),
            song.get('description', ''),
            song.get('lyrics', ''),
            song.get('url', ''),
            song.get('image_url', ''),
            song_id
        ))
        updated_count += 1
    else:
        # Insert new
        c.execute('''
        INSERT INTO songs (id, title, artist, description, lyrics, url, image_url, source_tab, suno_version, is_liked)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            song_id,
            song.get('title', ''),
            song.get('artist', ''),
            song.get('description', ''),
            song.get('lyrics', ''),
            song.get('url', ''),
            song.get('image_url', ''),
            'liked',
            'v3',
            1
        ))
        new_count += 1

conn.commit()
print(f"Inserted {new_count} new songs")
print(f"Updated {updated_count} existing songs")

# Verify total
c.execute('SELECT COUNT(*) FROM songs')
total = c.fetchone()[0]
print(f"Total songs in database: {total}")

conn.close()
