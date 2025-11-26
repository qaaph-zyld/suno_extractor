#!/usr/bin/env python3
"""
Suno Core - Configuration and Database Management
Central module for app configuration and persistent storage
"""

import os
import json
import sqlite3
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager

# YAML configuration
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


class Config:
    """Configuration management with YAML support"""
    
    DEFAULT_CONFIG = {
        'browser': {
            'type': 'chrome',
            'debug_port': 9222,
            'headless': False,
            'timeout': 30
        },
        'extraction': {
            'output_dir': 'suno_songs',
            'tabs': ['creations', 'likes'],
            'formats': ['json', 'csv', 'md'],
            'extract_details': True,
            'exclude_disliked': True,
            'scroll_pause': 1.2,
            'max_scrolls': 600
        },
        'download': {
            'output_dir': 'suno_downloads',
            'format': 'mp3',
            'max_workers': 3,
            'add_metadata': True,
            'download_cover_art': True,
            'cover_art_dir': 'suno_covers',
            'retry_attempts': 3,
            'retry_delay': 2
        },
        'audio_analysis': {
            'enabled': True,
            'detect_bpm': True,
            'detect_key': True,
            'generate_waveform': True,
            'waveform_dir': 'suno_waveforms',
            'waveform_width': 800,
            'waveform_height': 200
        },
        'database': {
            'path': 'suno_library.db',
            'backup_enabled': True,
            'backup_dir': 'backups'
        },
        'web_dashboard': {
            'enabled': True,
            'host': '127.0.0.1',
            'port': 5000,
            'debug': False
        },
        'player': {
            'backend': 'pygame',
            'default_volume': 0.7,
            'shuffle': False,
            'repeat': False
        },
        'logging': {
            'level': 'INFO',
            'file': 'suno_extractor.log',
            'console': True,
            'rich_formatting': True
        }
    }
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config = self.DEFAULT_CONFIG.copy()
        self.load()
    
    def load(self) -> Dict:
        """Load configuration from file"""
        if self.config_path.exists() and YAML_AVAILABLE:
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        self._deep_merge(self.config, file_config)
                logger.info(f"Loaded config from {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config: {e}, using defaults")
        return self.config
    
    def save(self):
        """Save current configuration to file"""
        if not YAML_AVAILABLE:
            logger.warning("YAML not available, cannot save config")
            return
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Saved config to {self.config_path}")
    
    def _deep_merge(self, base: Dict, override: Dict):
        """Deep merge override into base"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def get(self, *keys, default=None) -> Any:
        """Get nested config value"""
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value
    
    def set(self, value: Any, *keys):
        """Set nested config value"""
        config = self.config
        for key in keys[:-1]:
            config = config.setdefault(key, {})
        config[keys[-1]] = value


class SunoDatabase:
    """SQLite database for persistent storage of songs and metadata"""
    
    def __init__(self, db_path: str = "suno_library.db"):
        self.db_path = Path(db_path)
        self.connection = None
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Songs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS songs (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    artist TEXT,
                    description TEXT,
                    lyrics TEXT,
                    duration TEXT,
                    duration_seconds INTEGER,
                    url TEXT UNIQUE,
                    image_url TEXT,
                    local_audio_path TEXT,
                    local_cover_path TEXT,
                    source_tab TEXT,
                    suno_version TEXT,
                    created_at TEXT,
                    extracted_at TEXT,
                    downloaded_at TEXT,
                    file_size INTEGER,
                    audio_format TEXT,
                    bpm REAL,
                    musical_key TEXT,
                    energy REAL,
                    waveform_path TEXT,
                    is_liked INTEGER DEFAULT 0,
                    is_disliked INTEGER DEFAULT 0
                )
            ''')
            
            # Tags table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    song_id TEXT,
                    tag TEXT,
                    FOREIGN KEY (song_id) REFERENCES songs(id),
                    UNIQUE(song_id, tag)
                )
            ''')
            
            # Ratings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ratings (
                    song_id TEXT PRIMARY KEY,
                    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                    rated_at TEXT,
                    FOREIGN KEY (song_id) REFERENCES songs(id)
                )
            ''')
            
            # Play history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS play_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    song_id TEXT,
                    played_at TEXT,
                    duration_played INTEGER,
                    completed INTEGER DEFAULT 0,
                    FOREIGN KEY (song_id) REFERENCES songs(id)
                )
            ''')
            
            # Playlists table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    description TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    is_smart INTEGER DEFAULT 0,
                    smart_criteria TEXT
                )
            ''')
            
            # Playlist songs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS playlist_songs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER,
                    song_id TEXT,
                    position INTEGER,
                    added_at TEXT,
                    FOREIGN KEY (playlist_id) REFERENCES playlists(id),
                    FOREIGN KEY (song_id) REFERENCES songs(id),
                    UNIQUE(playlist_id, song_id)
                )
            ''')
            
            # Duplicates table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS duplicates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    song_id_1 TEXT,
                    song_id_2 TEXT,
                    similarity_score REAL,
                    duplicate_type TEXT,
                    detected_at TEXT,
                    FOREIGN KEY (song_id_1) REFERENCES songs(id),
                    FOREIGN KEY (song_id_2) REFERENCES songs(id),
                    UNIQUE(song_id_1, song_id_2)
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_songs_title ON songs(title)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_songs_artist ON songs(artist)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tags_song ON tags(song_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_play_history_song ON play_history(song_id)')
            
            conn.commit()
            logger.info(f"Database initialized: {self.db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def extract_song_id(self, url: str) -> Optional[str]:
        """Extract song ID from URL"""
        import re
        match = re.search(r'/song/([a-f0-9-]{36})', url)
        return match.group(1) if match else None
    
    def add_song(self, song: Dict) -> bool:
        """Add or update a song in the database"""
        song_id = self.extract_song_id(song.get('url', ''))
        if not song_id:
            return False
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Parse duration to seconds
            duration_seconds = self._parse_duration(song.get('duration', ''))
            
            # Determine suno version from tags
            suno_version = None
            for tag in song.get('tags', []):
                if tag.lower().startswith('v'):
                    suno_version = tag
                    break
            
            cursor.execute('''
                INSERT OR REPLACE INTO songs 
                (id, title, artist, description, lyrics, duration, duration_seconds,
                 url, image_url, source_tab, suno_version, extracted_at, is_liked, is_disliked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                song_id,
                song.get('title', ''),
                song.get('artist', ''),
                song.get('description', ''),
                song.get('lyrics', ''),
                song.get('duration', ''),
                duration_seconds,
                song.get('url', ''),
                song.get('image_url', ''),
                song.get('source_tab', ''),
                suno_version,
                datetime.now().isoformat(),
                1 if song.get('liked') else 0,
                1 if song.get('disliked') else 0
            ))
            
            # Add tags
            for tag in song.get('tags', []):
                if tag and not tag.lower().startswith('v'):  # Skip version tags
                    try:
                        cursor.execute('''
                            INSERT OR IGNORE INTO tags (song_id, tag) VALUES (?, ?)
                        ''', (song_id, tag))
                    except Exception:
                        pass
            
            conn.commit()
            return True
    
    def import_from_json(self, json_path: str) -> int:
        """Import songs from extraction JSON file"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        songs = data.get('songs', [])
        count = 0
        for song in songs:
            if self.add_song(song):
                count += 1
        
        logger.info(f"Imported {count} songs from {json_path}")
        return count
    
    def update_audio_info(self, song_id: str, audio_path: str = None,
                          cover_path: str = None, bpm: float = None,
                          key: str = None, waveform_path: str = None,
                          file_size: int = None, audio_format: str = None):
        """Update audio-related information for a song"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            updates = []
            values = []
            
            if audio_path:
                updates.append('local_audio_path = ?')
                values.append(audio_path)
                updates.append('downloaded_at = ?')
                values.append(datetime.now().isoformat())
            
            if cover_path:
                updates.append('local_cover_path = ?')
                values.append(cover_path)
            
            if bpm is not None:
                updates.append('bpm = ?')
                values.append(bpm)
            
            if key:
                updates.append('musical_key = ?')
                values.append(key)
            
            if waveform_path:
                updates.append('waveform_path = ?')
                values.append(waveform_path)
            
            if file_size:
                updates.append('file_size = ?')
                values.append(file_size)
            
            if audio_format:
                updates.append('audio_format = ?')
                values.append(audio_format)
            
            if updates:
                values.append(song_id)
                cursor.execute(
                    f"UPDATE songs SET {', '.join(updates)} WHERE id = ?",
                    values
                )
                conn.commit()
    
    def get_song(self, song_id: str) -> Optional[Dict]:
        """Get song by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM songs WHERE id = ?', (song_id,))
            row = cursor.fetchone()
            
            if row:
                song = dict(row)
                # Get tags
                cursor.execute('SELECT tag FROM tags WHERE song_id = ?', (song_id,))
                song['tags'] = [r['tag'] for r in cursor.fetchall()]
                return song
            
            return None
    
    def get_all_songs(self, limit: int = None, offset: int = 0) -> List[Dict]:
        """Get all songs with optional pagination"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM songs ORDER BY title'
            if limit:
                query += f' LIMIT {limit} OFFSET {offset}'
            
            cursor.execute(query)
            songs = []
            
            for row in cursor.fetchall():
                song = dict(row)
                cursor.execute('SELECT tag FROM tags WHERE song_id = ?', (song['id'],))
                song['tags'] = [r['tag'] for r in cursor.fetchall()]
                songs.append(song)
            
            return songs
    
    def search_songs(self, query: str, fields: List[str] = None) -> List[Dict]:
        """Search songs by query"""
        if fields is None:
            fields = ['title', 'artist', 'lyrics', 'description']
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            conditions = []
            params = []
            for field in fields:
                conditions.append(f'{field} LIKE ?')
                params.append(f'%{query}%')
            
            sql = f"SELECT * FROM songs WHERE {' OR '.join(conditions)}"
            cursor.execute(sql, params)
            
            songs = []
            for row in cursor.fetchall():
                song = dict(row)
                cursor.execute('SELECT tag FROM tags WHERE song_id = ?', (song['id'],))
                song['tags'] = [r['tag'] for r in cursor.fetchall()]
                songs.append(song)
            
            return songs
    
    def get_songs_by_tag(self, tag: str) -> List[Dict]:
        """Get all songs with a specific tag"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT s.* FROM songs s
                JOIN tags t ON s.id = t.song_id
                WHERE t.tag LIKE ?
            ''', (f'%{tag}%',))
            
            songs = []
            for row in cursor.fetchall():
                song = dict(row)
                cursor.execute('SELECT tag FROM tags WHERE song_id = ?', (song['id'],))
                song['tags'] = [r['tag'] for r in cursor.fetchall()]
                songs.append(song)
            
            return songs
    
    def rate_song(self, song_id: str, rating: int) -> bool:
        """Rate a song (1-5 stars)"""
        if not 1 <= rating <= 5:
            return False
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO ratings (song_id, rating, rated_at)
                VALUES (?, ?, ?)
            ''', (song_id, rating, datetime.now().isoformat()))
            conn.commit()
            return True
    
    def get_rating(self, song_id: str) -> Optional[int]:
        """Get song rating"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT rating FROM ratings WHERE song_id = ?', (song_id,))
            row = cursor.fetchone()
            return row['rating'] if row else None
    
    def record_play(self, song_id: str, duration_played: int = 0, completed: bool = False):
        """Record a play in history"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO play_history (song_id, played_at, duration_played, completed)
                VALUES (?, ?, ?, ?)
            ''', (song_id, datetime.now().isoformat(), duration_played, 1 if completed else 0))
            conn.commit()
    
    def get_play_count(self, song_id: str) -> int:
        """Get total play count for a song"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) as count FROM play_history WHERE song_id = ?',
                (song_id,)
            )
            row = cursor.fetchone()
            return row['count'] if row else 0
    
    def get_most_played(self, limit: int = 20) -> List[Dict]:
        """Get most played songs"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.*, COUNT(ph.id) as play_count
                FROM songs s
                LEFT JOIN play_history ph ON s.id = ph.song_id
                GROUP BY s.id
                ORDER BY play_count DESC
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_recently_played(self, limit: int = 20) -> List[Dict]:
        """Get recently played songs"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.*, ph.played_at as last_played
                FROM songs s
                JOIN play_history ph ON s.id = ph.song_id
                ORDER BY ph.played_at DESC
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def create_playlist(self, name: str, description: str = "",
                       is_smart: bool = False, criteria: str = None) -> int:
        """Create a new playlist"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO playlists (name, description, created_at, updated_at, is_smart, smart_criteria)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, description, now, now, 1 if is_smart else 0, criteria))
            conn.commit()
            return cursor.lastrowid
    
    def add_to_playlist(self, playlist_id: int, song_id: str) -> bool:
        """Add song to playlist"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get next position
            cursor.execute(
                'SELECT MAX(position) as max_pos FROM playlist_songs WHERE playlist_id = ?',
                (playlist_id,)
            )
            row = cursor.fetchone()
            position = (row['max_pos'] or 0) + 1
            
            try:
                cursor.execute('''
                    INSERT INTO playlist_songs (playlist_id, song_id, position, added_at)
                    VALUES (?, ?, ?, ?)
                ''', (playlist_id, song_id, position, datetime.now().isoformat()))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
    
    def get_playlist_songs(self, playlist_id: int) -> List[Dict]:
        """Get all songs in a playlist"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.*, ps.position
                FROM songs s
                JOIN playlist_songs ps ON s.id = ps.song_id
                WHERE ps.playlist_id = ?
                ORDER BY ps.position
            ''', (playlist_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def find_duplicates_by_title(self) -> List[Tuple[Dict, Dict, float]]:
        """Find potential duplicates by similar titles"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM songs ORDER BY title')
            songs = [dict(row) for row in cursor.fetchall()]
        
        duplicates = []
        for i, song1 in enumerate(songs):
            for song2 in songs[i+1:]:
                similarity = self._title_similarity(
                    song1.get('title', ''),
                    song2.get('title', '')
                )
                if similarity > 0.8:
                    duplicates.append((song1, song2, similarity))
        
        return duplicates
    
    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles"""
        if not title1 or not title2:
            return 0.0
        
        # Normalize titles
        t1 = title1.lower().strip()
        t2 = title2.lower().strip()
        
        if t1 == t2:
            return 1.0
        
        # Simple Jaccard similarity on words
        words1 = set(t1.split())
        words2 = set(t2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def get_statistics(self) -> Dict:
        """Get library statistics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Total songs
            cursor.execute('SELECT COUNT(*) as count FROM songs')
            stats['total_songs'] = cursor.fetchone()['count']
            
            # Total duration
            cursor.execute('SELECT SUM(duration_seconds) as total FROM songs')
            total_seconds = cursor.fetchone()['total'] or 0
            stats['total_duration_seconds'] = total_seconds
            hours = total_seconds // 3600
            mins = (total_seconds % 3600) // 60
            stats['total_duration_formatted'] = f"{hours}h {mins}m"
            
            # Downloaded songs
            cursor.execute('SELECT COUNT(*) as count FROM songs WHERE local_audio_path IS NOT NULL')
            stats['downloaded_songs'] = cursor.fetchone()['count']
            
            # Rated songs
            cursor.execute('SELECT COUNT(*) as count FROM ratings')
            stats['rated_songs'] = cursor.fetchone()['count']
            
            # Average rating
            cursor.execute('SELECT AVG(rating) as avg FROM ratings')
            stats['average_rating'] = round(cursor.fetchone()['avg'] or 0, 2)
            
            # Total plays
            cursor.execute('SELECT COUNT(*) as count FROM play_history')
            stats['total_plays'] = cursor.fetchone()['count']
            
            # Unique tags
            cursor.execute('SELECT COUNT(DISTINCT tag) as count FROM tags')
            stats['unique_tags'] = cursor.fetchone()['count']
            
            # Songs by version
            cursor.execute('''
                SELECT suno_version, COUNT(*) as count 
                FROM songs 
                WHERE suno_version IS NOT NULL 
                GROUP BY suno_version
            ''')
            stats['by_version'] = {row['suno_version']: row['count'] for row in cursor.fetchall()}
            
            # Top tags
            cursor.execute('''
                SELECT tag, COUNT(*) as count 
                FROM tags 
                GROUP BY tag 
                ORDER BY count DESC 
                LIMIT 10
            ''')
            stats['top_tags'] = {row['tag']: row['count'] for row in cursor.fetchall()}
            
            return stats
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to seconds"""
        try:
            parts = duration_str.split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except Exception:
            pass
        return 0
    
    def export_to_json(self, output_path: str) -> int:
        """Export database to JSON"""
        songs = self.get_all_songs()
        
        export_data = {
            'metadata': {
                'exported_at': datetime.now().isoformat(),
                'total_songs': len(songs),
                'source': 'suno_library.db'
            },
            'songs': songs
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return len(songs)
    
    def backup(self, backup_dir: str = "backups") -> Path:
        """Create database backup"""
        backup_path = Path(backup_dir)
        backup_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_path / f"suno_library_{timestamp}.db"
        
        import shutil
        shutil.copy2(self.db_path, backup_file)
        
        logger.info(f"Database backed up to: {backup_file}")
        return backup_file


# Singleton instances
_config = None
_database = None


def get_config() -> Config:
    """Get global config instance"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def get_database() -> SunoDatabase:
    """Get global database instance"""
    global _database
    if _database is None:
        config = get_config()
        db_path = config.get('database', 'path', default='suno_library.db')
        _database = SunoDatabase(db_path)
    return _database
