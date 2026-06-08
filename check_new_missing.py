#!/usr/bin/env python3
import json, sqlite3

with open('suno_songs/suno_liked_songs_20260608_232558.json', encoding='utf-8') as f:
    data = json.load(f)
songs = data['songs']

conn = sqlite3.connect('suno_library.db')
c = conn.cursor()
c.execute('SELECT id FROM songs WHERE local_audio_path IS NOT NULL AND length(local_audio_path)>0')
has_audio = {r[0] for r in c.fetchall()}
conn.close()

missing = [s for s in songs if s.get('id') not in has_audio]
print('Total in checkpoint: %d' % len(songs))
print('Already have audio: %d' % len([s for s in songs if s.get('id') in has_audio]))
print('Missing audio: %d' % len(missing))

if missing:
    with open('missing_new_songs.json', 'w', encoding='utf-8') as f:
        json.dump(missing, f, indent=2, ensure_ascii=False)
    print('Wrote missing_new_songs.json')
