#!/usr/bin/env python3
"""
Suno API Integration - Unofficial API support for better metadata
Integrates with Suno's internal APIs for richer data extraction
"""

import json
import re
import time
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class SunoAPI:
    """
    Unofficial Suno API client
    Extracts data from Suno's internal API endpoints
    """
    
    BASE_URL = "https://studio-api.suno.ai"
    CDN_URLS = [
        "https://cdn1.suno.ai",
        "https://cdn2.suno.ai", 
        "https://audiopipe.suno.ai"
    ]
    
    def __init__(self, cookie: str = None, session_id: str = None):
        """
        Initialize API client
        
        Args:
            cookie: Full cookie string from browser session
            session_id: Suno session ID (alternative to cookie)
        """
        self.session = self._create_session()
        self.cookie = cookie
        self.session_id = session_id
        self._auth_token = None
        
    def _create_session(self) -> requests.Session:
        """Create session with retry logic"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        # Default headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://suno.com',
            'Referer': 'https://suno.com/',
        })
        
        return session
    
    def set_cookie(self, cookie: str):
        """Set authentication cookie"""
        self.cookie = cookie
        self.session.headers['Cookie'] = cookie
    
    def extract_cookie_from_browser(self, driver) -> str:
        """Extract cookies from Selenium browser"""
        cookies = driver.get_cookies()
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        self.set_cookie(cookie_str)
        return cookie_str
    
    def get_user_info(self) -> Optional[Dict]:
        """Get current user information"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/api/user",
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
        return None
    
    def get_song_by_id(self, song_id: str) -> Optional[Dict]:
        """
        Get detailed song information by ID
        
        Args:
            song_id: Suno song UUID
            
        Returns:
            Song data dictionary
        """
        try:
            # Try multiple API endpoints
            endpoints = [
                f"{self.BASE_URL}/api/song/{song_id}",
                f"{self.BASE_URL}/api/clip/{song_id}",
                f"https://suno.com/api/song/{song_id}",
            ]
            
            for endpoint in endpoints:
                try:
                    response = self.session.get(endpoint, timeout=30)
                    if response.status_code == 200:
                        data = response.json()
                        return self._normalize_song_data(data)
                except Exception:
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to get song {song_id}: {e}")
        
        return None
    
    def get_liked_songs(self, page: int = 0, limit: int = 50) -> List[Dict]:
        """
        Get user's liked songs
        
        Args:
            page: Page number
            limit: Songs per page
            
        Returns:
            List of song dictionaries
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/api/feed/liked",
                params={'page': page, 'limit': limit},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                songs = data.get('clips', data.get('songs', []))
                return [self._normalize_song_data(s) for s in songs]
                
        except Exception as e:
            logger.error(f"Failed to get liked songs: {e}")
        
        return []
    
    def get_user_creations(self, page: int = 0, limit: int = 50) -> List[Dict]:
        """Get user's created songs"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/api/feed/my_creations",
                params={'page': page, 'limit': limit},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                songs = data.get('clips', data.get('songs', []))
                return [self._normalize_song_data(s) for s in songs]
                
        except Exception as e:
            logger.error(f"Failed to get creations: {e}")
        
        return []
    
    def get_all_liked_songs(self, max_pages: int = 100) -> List[Dict]:
        """Get all liked songs with pagination"""
        all_songs = []
        page = 0
        
        while page < max_pages:
            songs = self.get_liked_songs(page=page, limit=50)
            if not songs:
                break
            
            all_songs.extend(songs)
            logger.info(f"Fetched page {page + 1}, total: {len(all_songs)} songs")
            
            if len(songs) < 50:  # Last page
                break
            
            page += 1
            time.sleep(0.5)  # Rate limiting
        
        return all_songs
    
    def _normalize_song_data(self, data: Dict) -> Dict:
        """Normalize song data from various API formats"""
        if not data:
            return {}
        
        # Handle nested structures
        if 'clip' in data:
            data = data['clip']
        if 'song' in data:
            data = data['song']
        
        song_id = data.get('id', data.get('clip_id', data.get('song_id', '')))
        
        return {
            'id': song_id,
            'title': data.get('title', data.get('name', '')),
            'artist': data.get('display_name', data.get('handle', data.get('user', {}).get('display_name', 'Suno AI'))),
            'description': data.get('prompt', data.get('description', data.get('gpt_description_prompt', ''))),
            'lyrics': data.get('lyrics', data.get('text', '')),
            'tags': self._extract_tags(data),
            'duration': self._format_duration(data.get('duration', data.get('audio_duration', 0))),
            'duration_seconds': data.get('duration', data.get('audio_duration', 0)),
            'url': f"https://suno.com/song/{song_id}",
            'audio_url': data.get('audio_url', data.get('audio_file', '')),
            'video_url': data.get('video_url', data.get('video_file', '')),
            'image_url': data.get('image_url', data.get('image_large_url', data.get('cover_image_url', ''))),
            'created_at': data.get('created_at', data.get('created', '')),
            'plays': data.get('play_count', data.get('plays', 0)),
            'likes': data.get('upvote_count', data.get('likes', 0)),
            'is_public': data.get('is_public', True),
            'model_version': data.get('model_name', data.get('major_model_version', '')),
            'status': data.get('status', 'complete'),
            'raw_data': data  # Keep original for debugging
        }
    
    def _extract_tags(self, data: Dict) -> List[str]:
        """Extract tags from song data"""
        tags = []
        
        # Direct tags
        if 'tags' in data:
            if isinstance(data['tags'], list):
                tags.extend(data['tags'])
            elif isinstance(data['tags'], str):
                tags.extend([t.strip() for t in data['tags'].split(',')])
        
        # Style/genre
        if 'style' in data:
            tags.append(data['style'])
        
        # Model version as tag
        if 'major_model_version' in data:
            tags.append(f"v{data['major_model_version']}")
        elif 'model_name' in data:
            tags.append(data['model_name'])
        
        return list(set(filter(None, tags)))
    
    def _format_duration(self, seconds) -> str:
        """Format duration in MM:SS"""
        try:
            seconds = float(seconds)
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}:{secs:02d}"
        except Exception:
            return ""
    
    def get_audio_url(self, song_id: str, prefer_quality: str = 'high') -> Optional[str]:
        """
        Get audio download URL for a song
        
        Args:
            song_id: Song UUID
            prefer_quality: 'high', 'medium', or 'low'
            
        Returns:
            Audio URL or None
        """
        # Try CDN patterns
        cdn_patterns = [
            f"https://cdn1.suno.ai/{song_id}.mp3",
            f"https://cdn2.suno.ai/{song_id}.mp3",
            f"https://audiopipe.suno.ai/item_id/{song_id}",
            f"https://cdn1.suno.ai/{song_id}.m4a",
        ]
        
        for url in cdn_patterns:
            try:
                response = self.session.head(url, timeout=10, allow_redirects=True)
                if response.status_code == 200:
                    return url
            except Exception:
                continue
        
        # Try API endpoint
        song_data = self.get_song_by_id(song_id)
        if song_data and song_data.get('audio_url'):
            return song_data['audio_url']
        
        return None
    
    def download_audio(self, song_id: str, output_path: str,
                       retry_count: int = 3) -> bool:
        """
        Download audio file with retry logic
        
        Args:
            song_id: Song UUID
            output_path: Output file path
            retry_count: Number of retries
            
        Returns:
            True if successful
        """
        audio_url = self.get_audio_url(song_id)
        if not audio_url:
            logger.error(f"No audio URL found for {song_id}")
            return False
        
        for attempt in range(retry_count):
            try:
                response = self.session.get(
                    audio_url,
                    stream=True,
                    timeout=60
                )
                response.raise_for_status()
                
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                logger.info(f"Downloaded: {output_path}")
                return True
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        return False
    
    def batch_download(self, songs: List[Dict], output_dir: str,
                       max_workers: int = 3) -> Dict[str, bool]:
        """
        Download multiple songs in parallel
        
        Args:
            songs: List of song dictionaries
            output_dir: Output directory
            max_workers: Parallel downloads
            
        Returns:
            Dict mapping song_id to success status
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = {}
        
        def download_one(song):
            song_id = song.get('id')
            title = song.get('title', song_id)
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:100]
            output_path = output_dir / f"{safe_title}.mp3"
            
            success = self.download_audio(song_id, str(output_path))
            return song_id, success
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(download_one, song): song for song in songs}
            
            for future in as_completed(futures):
                song_id, success = future.result()
                results[song_id] = success
        
        successful = sum(1 for v in results.values() if v)
        logger.info(f"Downloaded {successful}/{len(songs)} songs")
        
        return results


class SunoSync:
    """
    Real-time sync watcher for Suno library
    Monitors for new songs and auto-extracts
    """
    
    def __init__(self, api: SunoAPI, db=None, check_interval: int = 300):
        """
        Initialize sync watcher
        
        Args:
            api: SunoAPI instance
            db: Database instance
            check_interval: Seconds between checks
        """
        self.api = api
        self.db = db
        self.check_interval = check_interval
        self._running = False
        self._known_ids = set()
    
    def load_known_ids(self):
        """Load existing song IDs from database"""
        if self.db:
            songs = self.db.get_all_songs()
            self._known_ids = {s.get('id') for s in songs if s.get('id')}
        logger.info(f"Loaded {len(self._known_ids)} known song IDs")
    
    def check_for_new_songs(self) -> List[Dict]:
        """Check for new songs since last sync"""
        new_songs = []
        
        # Check liked songs
        liked = self.api.get_liked_songs(page=0, limit=20)
        for song in liked:
            if song.get('id') not in self._known_ids:
                new_songs.append(song)
                self._known_ids.add(song.get('id'))
        
        # Check creations
        creations = self.api.get_user_creations(page=0, limit=20)
        for song in creations:
            if song.get('id') not in self._known_ids:
                new_songs.append(song)
                self._known_ids.add(song.get('id'))
        
        return new_songs
    
    def sync_once(self) -> List[Dict]:
        """Run single sync check"""
        new_songs = self.check_for_new_songs()
        
        if new_songs:
            logger.info(f"Found {len(new_songs)} new songs")
            
            # Add to database
            if self.db:
                for song in new_songs:
                    self.db.add_song(song)
        
        return new_songs
    
    def start(self, callback=None):
        """
        Start continuous sync
        
        Args:
            callback: Function to call with new songs
        """
        self._running = True
        self.load_known_ids()
        
        logger.info(f"Starting sync watcher (interval: {self.check_interval}s)")
        
        while self._running:
            try:
                new_songs = self.sync_once()
                
                if new_songs and callback:
                    callback(new_songs)
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Sync error: {e}")
                time.sleep(30)  # Wait before retry
        
        logger.info("Sync watcher stopped")
    
    def stop(self):
        """Stop sync watcher"""
        self._running = False


class SmartPlaylistGenerator:
    """Generate smart playlists based on audio features"""
    
    def __init__(self, db=None):
        self.db = db
    
    def by_bpm_range(self, min_bpm: float, max_bpm: float,
                     name: str = None) -> List[Dict]:
        """Get songs within BPM range"""
        if not self.db:
            return []
        
        songs = self.db.get_all_songs()
        filtered = [
            s for s in songs
            if s.get('bpm') and min_bpm <= s['bpm'] <= max_bpm
        ]
        
        return sorted(filtered, key=lambda x: x.get('bpm', 0))
    
    def by_key(self, musical_key: str) -> List[Dict]:
        """Get songs in a specific key"""
        if not self.db:
            return []
        
        songs = self.db.get_all_songs()
        key_lower = musical_key.lower()
        
        return [
            s for s in songs
            if s.get('musical_key') and key_lower in s['musical_key'].lower()
        ]
    
    def by_mood(self, mood: str) -> List[Dict]:
        """
        Get songs by mood (based on tags and BPM)
        
        Moods: energetic, chill, melancholic, happy, aggressive
        """
        if not self.db:
            return []
        
        songs = self.db.get_all_songs()
        
        mood_filters = {
            'energetic': lambda s: s.get('bpm', 0) > 120 or any(
                t in str(s.get('tags', [])).lower() 
                for t in ['energetic', 'upbeat', 'dance', 'electronic']
            ),
            'chill': lambda s: s.get('bpm', 0) < 100 or any(
                t in str(s.get('tags', [])).lower()
                for t in ['chill', 'ambient', 'relaxing', 'lofi']
            ),
            'melancholic': lambda s: any(
                t in str(s.get('tags', [])).lower()
                for t in ['sad', 'melancholic', 'emotional', 'ballad']
            ) or (s.get('musical_key', '').lower().endswith('minor')),
            'happy': lambda s: any(
                t in str(s.get('tags', [])).lower()
                for t in ['happy', 'uplifting', 'joyful', 'fun']
            ) or (s.get('musical_key', '').lower().endswith('major')),
            'aggressive': lambda s: s.get('bpm', 0) > 140 or any(
                t in str(s.get('tags', [])).lower()
                for t in ['metal', 'rock', 'aggressive', 'heavy']
            ),
        }
        
        filter_func = mood_filters.get(mood.lower(), lambda s: True)
        return [s for s in songs if filter_func(s)]
    
    def workout_playlist(self, duration_minutes: int = 60) -> List[Dict]:
        """Generate workout playlist with high BPM songs"""
        energetic = self.by_bpm_range(120, 200)
        
        # Sort by BPM to build intensity
        playlist = []
        total_duration = 0
        target_seconds = duration_minutes * 60
        
        # Warmup: lower BPM
        warmup = [s for s in energetic if 120 <= s.get('bpm', 0) <= 130]
        for s in warmup[:3]:
            if total_duration < target_seconds * 0.1:
                playlist.append(s)
                total_duration += s.get('duration_seconds', 180)
        
        # Main: high BPM
        main = sorted(energetic, key=lambda x: x.get('bpm', 0), reverse=True)
        for s in main:
            if total_duration < target_seconds * 0.85:
                if s not in playlist:
                    playlist.append(s)
                    total_duration += s.get('duration_seconds', 180)
        
        # Cooldown: lower BPM
        cooldown = self.by_bpm_range(80, 110)
        for s in cooldown[:3]:
            if total_duration < target_seconds:
                playlist.append(s)
                total_duration += s.get('duration_seconds', 180)
        
        return playlist
    
    def similar_songs(self, song_id: str, limit: int = 10) -> List[Dict]:
        """Find songs similar to a given song"""
        if not self.db:
            return []
        
        target = self.db.get_song(song_id)
        if not target:
            return []
        
        songs = self.db.get_all_songs()
        
        # Score similarity
        scored = []
        for s in songs:
            if s.get('id') == song_id:
                continue
            
            score = 0
            
            # BPM similarity (0-30 points)
            if target.get('bpm') and s.get('bpm'):
                bpm_diff = abs(target['bpm'] - s['bpm'])
                score += max(0, 30 - bpm_diff)
            
            # Key similarity (0-25 points)
            if target.get('musical_key') and s.get('musical_key'):
                if target['musical_key'] == s['musical_key']:
                    score += 25
                elif target['musical_key'].split()[0] == s['musical_key'].split()[0]:
                    score += 15
            
            # Tag overlap (0-30 points)
            target_tags = set(target.get('tags', []))
            song_tags = set(s.get('tags', []))
            if target_tags and song_tags:
                overlap = len(target_tags & song_tags)
                score += min(30, overlap * 10)
            
            # Same artist (0-15 points)
            if target.get('artist') == s.get('artist'):
                score += 15
            
            scored.append((s, score))
        
        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return [s for s, _ in scored[:limit]]


def main():
    """Demo and testing"""
    import argparse
    
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(description="Suno API Tools")
    parser.add_argument('command', choices=['test', 'liked', 'creations', 'sync', 'download'])
    parser.add_argument('--cookie', help='Browser cookie string')
    parser.add_argument('--song-id', help='Song ID for specific operations')
    parser.add_argument('--output', default='suno_downloads', help='Output directory')
    
    args = parser.parse_args()
    
    api = SunoAPI()
    
    if args.cookie:
        api.set_cookie(args.cookie)
    
    if args.command == 'test':
        print("Testing API connection...")
        user = api.get_user_info()
        if user:
            print(f"Connected as: {user.get('display_name', 'Unknown')}")
        else:
            print("Not authenticated or API unavailable")
    
    elif args.command == 'liked':
        songs = api.get_liked_songs()
        print(f"Found {len(songs)} liked songs")
        for s in songs[:5]:
            print(f"  - {s.get('title')} ({s.get('duration')})")
    
    elif args.command == 'creations':
        songs = api.get_user_creations()
        print(f"Found {len(songs)} creations")
        for s in songs[:5]:
            print(f"  - {s.get('title')} ({s.get('duration')})")
    
    elif args.command == 'download' and args.song_id:
        success = api.download_audio(args.song_id, f"{args.output}/{args.song_id}.mp3")
        print(f"Download {'successful' if success else 'failed'}")
    
    elif args.command == 'sync':
        sync = SunoSync(api)
        sync.sync_once()


if __name__ == "__main__":
    main()
