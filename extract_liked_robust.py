#!/usr/bin/env python3
"""Extract liked songs with incremental saving."""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import requests
import json
import sqlite3
import time

options = Options()
options.add_experimental_option('debuggerAddress', '127.0.0.1:9222')
driver = webdriver.Chrome(options=options)

# Get session token
cookies = driver.get_cookies()
session_token = None
for c in cookies:
    if c['name'] == '__session':
        session_token = c['value']
        break

driver.quit()

if not session_token:
    print('No session token')
    exit(1)

headers = {
    'Authorization': f'Bearer {session_token}',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://suno.com/playlist/liked',
    'Origin': 'https://suno.com'
}

conn = sqlite3.connect('suno_library.db')
c = conn.cursor()

# Reset is_liked
c.execute('UPDATE songs SET is_liked=0')
conn.commit()
print('Reset is_liked flags')

seen_ids = set()
all_clips = []
cursor = None
page = 1

while True:
    payload = {'type': 'liked'}
    if cursor:
        payload['cursor'] = cursor
    
    try:
        resp = requests.post(
            'https://studio-api-prod.suno.com/api/feed/v3',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if resp.status_code != 200:
            print(f'Error status {resp.status_code}: {resp.text[:100]}')
            break
        
        data = resp.json()
        clips = data.get('clips', [])
        has_more = data.get('has_more', False)
        cursor = data.get('next_cursor')
        
        if not clips:
            break
        
        new_clips = [c for c in clips if c.get('id') and c['id'] not in seen_ids]
        if not new_clips:
            print('No new clips, stopping')
            break
        
        for clip in new_clips:
            seen_ids.add(clip['id'])
            all_clips.append(clip)
            
            # Insert/update immediately
            song_id = clip['id']
            title = clip.get('title', '')
            
            c.execute('SELECT id FROM songs WHERE id = ?', (song_id,))
            if c.fetchone():
                c.execute('UPDATE songs SET is_liked=1 WHERE id = ?', (song_id,))
            else:
                c.execute(
                    'INSERT OR IGNORE INTO songs (id, title, url, is_liked) VALUES (?, ?, ?, 1)',
                    (song_id, title, f'https://suno.com/song/{song_id}')
                )
        
        conn.commit()
        print(f'Page {page}: +{len(new_clips)} new = {len(all_clips)} total')
        
        # Save incremental JSON
        with open('suno_songs/liked_extract_progress.json', 'w', encoding='utf-8') as f:
            json.dump({'songs': all_clips, 'page': page}, f, indent=2, ensure_ascii=False)
        
        if not has_more:
            print('has_more is false')
            break
        
        page += 1
        time.sleep(0.3)
        
    except Exception as e:
        print(f'Error: {e}')
        break

print(f'\nDone! Total unique liked songs: {len(all_clips)}')

c.execute('SELECT COUNT(*) FROM songs WHERE is_liked=1')
print(f'Liked in DB: {c.fetchone()[0]}')
conn.close()

# Save final
with open('suno_songs/all_liked_songs.json', 'w', encoding='utf-8') as f:
    json.dump({'songs': all_clips}, f, indent=2, ensure_ascii=False)
print('Saved to suno_songs/all_liked_songs.json')
