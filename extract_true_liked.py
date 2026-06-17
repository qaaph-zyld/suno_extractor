#!/usr/bin/env python3
"""Extract only truly liked songs by filtering is_liked=True."""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import requests
import json
import sqlite3
import time

options = Options()
options.add_experimental_option('debuggerAddress', '127.0.0.1:9222')
driver = webdriver.Chrome(options=options)

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
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://suno.com/playlist/liked',
    'Origin': 'https://suno.com'
}

conn = sqlite3.connect('suno_library.db')
c = conn.cursor()
c.execute('UPDATE songs SET is_liked=0')
conn.commit()

liked_ids = set()
all_liked_clips = []
cursor = None
page = 1
empty_pages = 0
max_empty = 5  # Stop after 5 pages with no new liked songs

while empty_pages < max_empty:
    payload = {'type': 'liked', 'limit': 100}
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
            print(f'Error: {resp.status_code}')
            break
        
        data = resp.json()
        clips = data.get('clips', [])
        has_more = data.get('has_more', False)
        cursor = data.get('next_cursor')
        
        if not clips:
            break
        
        # Filter to only truly liked songs
        new_liked = []
        for clip in clips:
            if clip.get('is_liked') and clip.get('id') and clip['id'] not in liked_ids:
                liked_ids.add(clip['id'])
                new_liked.append(clip)
        
        if new_liked:
            all_liked_clips.extend(new_liked)
            empty_pages = 0
            
            # Update DB
            for clip in new_liked:
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
            
            print(f'Page {page}: +{len(new_liked)} liked = {len(all_liked_clips)} total')
        else:
            empty_pages += 1
            print(f'Page {page}: 0 new liked ({empty_pages}/{max_empty} empty)')
        
        if not has_more:
            print('has_more is false')
            break
        
        page += 1
        time.sleep(0.2)
        
    except Exception as e:
        print(f'Error: {e}')
        break

print(f'\nDone! Total truly liked songs: {len(all_liked_clips)}')
c.execute('SELECT COUNT(*) FROM songs WHERE is_liked=1')
print(f'DB liked: {c.fetchone()[0]}')
conn.close()

# Save
with open('suno_songs/all_liked_songs.json', 'w', encoding='utf-8') as f:
    json.dump({'songs': all_liked_clips}, f, indent=2, ensure_ascii=False)
print('Saved to suno_songs/all_liked_songs.json')
