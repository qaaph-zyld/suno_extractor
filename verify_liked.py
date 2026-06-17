#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect("suno_library.db")
c = conn.cursor()

c.execute('SELECT COUNT(*) FROM songs WHERE is_liked=1')
liked = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM songs WHERE is_liked=0')
not_liked = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM songs WHERE is_liked=1 AND (lyrics IS NULL OR lyrics="")')
missing_lyrics = c.fetchone()[0]

print('Liked songs: %d' % liked)
print('Not liked: %d' % not_liked)
print('Liked missing lyrics: %d' % missing_lyrics)

print('\n--- First 10 songs in extraction queue ---')
c.execute('SELECT id, title, url FROM songs WHERE is_liked=1 AND (lyrics IS NULL OR lyrics="") LIMIT 10')
for i, row in enumerate(c.fetchall(), 1):
    print('%d. %s | %s' % (i, row[1][:50], row[2]))

conn.close()
