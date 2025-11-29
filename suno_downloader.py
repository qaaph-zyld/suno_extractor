#!/usr/bin/env python3
"""
Suno Audio Downloader & Manager
Downloads audio files from Suno CDN with metadata tagging
"""

import json
import os
import re
import time
import logging
import requests
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# Audio metadata handling
try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, COMM, APIC, USLT, TDRC
    from mutagen.mp4 import MP4, MP4Cover
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

# Audio conversion
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

logger = logging.getLogger(__name__)


class SunoDownloader:
    """Download and manage Suno audio files"""
    
    # Known Suno CDN patterns
    CDN_AUDIO_PATTERNS = [
        "https://cdn1.suno.ai/",
        "https://cdn2.suno.ai/",
        "https://audiopipe.suno.ai/",
    ]
    
    def __init__(self, download_dir: str = "suno_downloads"):
        """
        Initialize downloader
        
        Args:
            download_dir: Directory to save downloaded files
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def extract_song_id(self, url: str) -> Optional[str]:
        """Extract song ID from Suno URL"""
        patterns = [
            r'/song/([a-f0-9-]{36})',
            r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def get_audio_urls(self, song_id: str) -> Dict[str, str]:
        """
        Get direct audio URLs for a song
        
        Args:
            song_id: Suno song UUID
            
        Returns:
            Dict with format -> URL mappings
        """
        urls = {}
        
        # Try different CDN patterns and formats
        formats = [
            ('mp3', f'{song_id}.mp3'),
            ('mp3_alt', f'audio_{song_id}.mp3'),
            ('m4a', f'{song_id}.m4a'),
            ('wav', f'{song_id}.wav'),
        ]
        
        for cdn in self.CDN_AUDIO_PATTERNS:
            for fmt, filename in formats:
                url = f"{cdn}{filename}"
                try:
                    response = self.session.head(url, timeout=5, allow_redirects=True)
                    if response.status_code == 200:
                        content_length = response.headers.get('content-length', 0)
                        if int(content_length) > 10000:  # Valid audio file
                            urls[fmt.replace('_alt', '')] = url
                            logger.debug(f"Found audio: {url}")
                except Exception:
                    continue
                    
        return urls
    
    def download_audio(self, song: Dict, format: str = 'mp3', 
                       add_metadata: bool = True) -> Optional[Path]:
        """
        Download audio file for a song
        
        Args:
            song: Song metadata dict
            format: Preferred format (mp3, m4a, wav)
            add_metadata: Whether to add ID3 tags
            
        Returns:
            Path to downloaded file or None
        """
        song_id = self.extract_song_id(song.get('url', ''))
        if not song_id:
            logger.error(f"Could not extract song ID from URL: {song.get('url')}")
            return None
        
        # Get available audio URLs
        audio_urls = self.get_audio_urls(song_id)
        if not audio_urls:
            logger.warning(f"No audio URLs found for: {song.get('title', song_id)}")
            return None
        
        # Generate safe filename
        title = song.get('title', song_id)
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:100]
        
        # For WAV: check if WAV already exists, otherwise download source and convert
        want_wav = format.lower() == 'wav'
        wav_filename = f"{safe_title}.wav"
        wav_filepath = self.download_dir / wav_filename
        
        if want_wav and wav_filepath.exists():
            logger.info(f"Already exists: {wav_filename}")
            return wav_filepath
        
        # Select best available source format (prefer mp3 for conversion)
        source_format = 'mp3' if 'mp3' in audio_urls else list(audio_urls.keys())[0]
        url = audio_urls[source_format]
        
        # If not wanting WAV, use requested format if available
        if not want_wav:
            source_format = format if format in audio_urls else source_format
            url = audio_urls.get(format, url)
        
        source_filename = f"{safe_title}.{source_format}"
        source_filepath = self.download_dir / source_filename
        
        # Check if source already exists (for non-WAV requests)
        if not want_wav and source_filepath.exists():
            logger.info(f"Already exists: {source_filename}")
            return source_filepath
        
        # Download source file
        try:
            # Only download if source doesn't exist
            if not source_filepath.exists():
                logger.info(f"Downloading: {title}")
                response = self.session.get(url, stream=True, timeout=60)
                response.raise_for_status()
                
                with open(source_filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                logger.info(f"Downloaded: {source_filename}")
                
                # Add metadata if requested
                if add_metadata and MUTAGEN_AVAILABLE:
                    self.add_metadata(source_filepath, song)
            
            # Convert to WAV if requested
            if want_wav:
                if not PYDUB_AVAILABLE:
                    logger.warning("pydub not available - cannot convert to WAV, keeping source format")
                    return source_filepath
                
                logger.info(f"Converting to WAV: {title}")
                try:
                    audio = AudioSegment.from_file(str(source_filepath), format=source_format)
                    audio.export(str(wav_filepath), format='wav')
                    logger.info(f"Converted: {wav_filename}")
                    return wav_filepath
                except Exception as conv_err:
                    logger.error(f"WAV conversion failed: {conv_err}")
                    return source_filepath
            
            return source_filepath
            
        except Exception as e:
            logger.error(f"Failed to download {title}: {e}")
            if source_filepath.exists():
                source_filepath.unlink()
            return None
    
    def add_metadata(self, filepath: Path, song: Dict) -> bool:
        """
        Add ID3 metadata tags to audio file
        
        Args:
            filepath: Path to audio file
            song: Song metadata dict
            
        Returns:
            Success status
        """
        if not MUTAGEN_AVAILABLE:
            logger.warning("Mutagen not available - skipping metadata")
            return False
        
        try:
            ext = filepath.suffix.lower()
            
            if ext == '.mp3':
                return self._tag_mp3(filepath, song)
            elif ext in ('.m4a', '.mp4'):
                return self._tag_m4a(filepath, song)
            else:
                logger.debug(f"Unsupported format for tagging: {ext}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to add metadata: {e}")
            return False
    
    def _tag_mp3(self, filepath: Path, song: Dict) -> bool:
        """Add ID3 tags to MP3 file"""
        try:
            audio = MP3(str(filepath))
            
            # Initialize ID3 if not present
            try:
                audio.add_tags()
            except Exception:
                pass
            
            tags = audio.tags
            if tags is None:
                return False
            
            # Add tags
            tags['TIT2'] = TIT2(encoding=3, text=song.get('title', 'Unknown'))
            tags['TPE1'] = TPE1(encoding=3, text=song.get('artist', 'Suno AI'))
            tags['TALB'] = TALB(encoding=3, text='Suno AI Creations')
            
            # Genre from tags
            if song.get('tags'):
                tags['TCON'] = TCON(encoding=3, text=', '.join(song.get('tags', [])))
            
            # Lyrics
            if song.get('lyrics'):
                tags['USLT'] = USLT(encoding=3, lang='eng', desc='', 
                                   text=song.get('lyrics', ''))
            
            # Description as comment
            if song.get('description'):
                tags['COMM'] = COMM(encoding=3, lang='eng', desc='Prompt',
                                   text=song.get('description', ''))
            
            # Download and embed cover art
            if song.get('image_url'):
                try:
                    img_response = self.session.get(song['image_url'], timeout=10)
                    if img_response.status_code == 200:
                        tags['APIC'] = APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3,  # Front cover
                            desc='Cover',
                            data=img_response.content
                        )
                except Exception:
                    pass
            
            audio.save()
            logger.debug(f"Tagged: {filepath.name}")
            return True
            
        except Exception as e:
            logger.error(f"MP3 tagging failed: {e}")
            return False
    
    def _tag_m4a(self, filepath: Path, song: Dict) -> bool:
        """Add tags to M4A file"""
        try:
            audio = MP4(str(filepath))
            
            audio['\xa9nam'] = song.get('title', 'Unknown')
            audio['\xa9ART'] = song.get('artist', 'Suno AI')
            audio['\xa9alb'] = 'Suno AI Creations'
            
            if song.get('tags'):
                audio['\xa9gen'] = ', '.join(song.get('tags', []))
            
            if song.get('description'):
                audio['\xa9cmt'] = song.get('description', '')
            
            # Cover art
            if song.get('image_url'):
                try:
                    img_response = self.session.get(song['image_url'], timeout=10)
                    if img_response.status_code == 200:
                        audio['covr'] = [MP4Cover(img_response.content, 
                                                  imageformat=MP4Cover.FORMAT_JPEG)]
                except Exception:
                    pass
            
            audio.save()
            logger.debug(f"Tagged: {filepath.name}")
            return True
            
        except Exception as e:
            logger.error(f"M4A tagging failed: {e}")
            return False
    
    def download_collection(self, songs: List[Dict], format: str = 'mp3',
                           max_workers: int = 3, 
                           add_metadata: bool = True) -> Dict[str, List]:
        """
        Download multiple songs with parallel execution
        
        Args:
            songs: List of song metadata dicts
            format: Preferred format
            max_workers: Parallel download threads
            add_metadata: Add ID3 tags
            
        Returns:
            Dict with 'success' and 'failed' lists
        """
        results = {'success': [], 'failed': []}
        
        logger.info(f"Downloading {len(songs)} songs...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.download_audio, song, format, add_metadata): song
                for song in songs
            }
            
            for future in as_completed(futures):
                song = futures[future]
                try:
                    filepath = future.result()
                    if filepath:
                        results['success'].append({
                            'song': song,
                            'path': str(filepath)
                        })
                    else:
                        results['failed'].append(song)
                except Exception as e:
                    logger.error(f"Download task failed: {e}")
                    results['failed'].append(song)
        
        logger.info(f"✓ Downloaded: {len(results['success'])}")
        logger.info(f"✗ Failed: {len(results['failed'])}")
        
        return results
    
    def download_from_json(self, json_path: str, format: str = 'mp3') -> Dict[str, List]:
        """
        Download all songs from an extraction JSON file
        
        Args:
            json_path: Path to JSON file from extractor
            format: Preferred format
            
        Returns:
            Download results
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        songs = data.get('songs', [])
        return self.download_collection(songs, format)


class PlaylistManager:
    """Manage playlists and M3U export"""
    
    def __init__(self, output_dir: str = "suno_playlists"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def create_m3u(self, songs: List[Dict], name: str = "suno_playlist",
                   audio_dir: str = None) -> Path:
        """
        Create M3U playlist file
        
        Args:
            songs: List of song dicts with file paths
            name: Playlist name
            audio_dir: Directory containing audio files
            
        Returns:
            Path to created playlist
        """
        filepath = self.output_dir / f"{name}.m3u"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n\n")
            
            for song in songs:
                title = song.get('title', 'Unknown')
                artist = song.get('artist', 'Suno AI')
                duration = self._parse_duration(song.get('duration', '0:00'))
                
                # Determine file path
                if 'path' in song:
                    audio_path = song['path']
                elif audio_dir:
                    safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:100]
                    audio_path = str(Path(audio_dir) / f"{safe_title}.mp3")
                else:
                    continue
                
                f.write(f"#EXTINF:{duration},{artist} - {title}\n")
                f.write(f"{audio_path}\n\n")
        
        logger.info(f"✓ Created playlist: {filepath}")
        return filepath
    
    def create_m3u_from_json(self, json_path: str, audio_dir: str = "suno_downloads",
                             name: str = None) -> Path:
        """Create M3U from extraction JSON"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        songs = data.get('songs', [])
        playlist_name = name or Path(json_path).stem
        
        return self.create_m3u(songs, playlist_name, audio_dir)
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string (MM:SS) to seconds"""
        try:
            parts = duration_str.split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except Exception:
            pass
        return 0


class CollectionAnalyzer:
    """Analyze and search local Suno collection"""
    
    def __init__(self, collection_path: str = None):
        """
        Initialize analyzer
        
        Args:
            collection_path: Path to JSON collection file
        """
        self.songs = []
        if collection_path:
            self.load_collection(collection_path)
    
    def load_collection(self, json_path: str):
        """Load songs from JSON file"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.songs = data.get('songs', [])
        logger.info(f"Loaded {len(self.songs)} songs")
    
    def search(self, query: str, fields: List[str] = None) -> List[Dict]:
        """
        Search songs by query
        
        Args:
            query: Search text
            fields: Fields to search (default: title, artist, tags, description)
            
        Returns:
            Matching songs
        """
        if fields is None:
            fields = ['title', 'artist', 'tags', 'description', 'lyrics']
        
        query_lower = query.lower()
        results = []
        
        for song in self.songs:
            for field in fields:
                value = song.get(field, '')
                if isinstance(value, list):
                    value = ' '.join(value)
                if query_lower in str(value).lower():
                    results.append(song)
                    break
        
        return results
    
    def filter_by_tags(self, tags: List[str], match_all: bool = False) -> List[Dict]:
        """Filter songs by tags"""
        results = []
        for song in self.songs:
            song_tags = [t.lower() for t in song.get('tags', [])]
            search_tags = [t.lower() for t in tags]
            
            if match_all:
                if all(t in song_tags for t in search_tags):
                    results.append(song)
            else:
                if any(t in song_tags for t in search_tags):
                    results.append(song)
        
        return results
    
    def filter_by_duration(self, min_seconds: int = 0, 
                          max_seconds: int = float('inf')) -> List[Dict]:
        """Filter songs by duration range"""
        results = []
        for song in self.songs:
            duration = self._parse_duration(song.get('duration', '0:00'))
            if min_seconds <= duration <= max_seconds:
                results.append(song)
        return results
    
    def get_statistics(self) -> Dict:
        """Get collection statistics"""
        stats = {
            'total_songs': len(self.songs),
            'total_duration_seconds': 0,
            'total_duration_formatted': '',
            'with_lyrics': 0,
            'with_description': 0,
            'tags_distribution': {},
            'version_distribution': {},
            'source_tab_distribution': {},
            'avg_duration_seconds': 0
        }
        
        for song in self.songs:
            # Duration
            duration = self._parse_duration(song.get('duration', '0:00'))
            stats['total_duration_seconds'] += duration
            
            # Content flags
            if song.get('lyrics'):
                stats['with_lyrics'] += 1
            if song.get('description'):
                stats['with_description'] += 1
            
            # Tags
            for tag in song.get('tags', []):
                stats['tags_distribution'][tag] = stats['tags_distribution'].get(tag, 0) + 1
            
            # Source tab
            tab = song.get('source_tab', 'unknown')
            stats['source_tab_distribution'][tab] = stats['source_tab_distribution'].get(tab, 0) + 1
        
        # Calculate averages
        if stats['total_songs'] > 0:
            stats['avg_duration_seconds'] = stats['total_duration_seconds'] / stats['total_songs']
        
        # Format total duration
        total_mins = stats['total_duration_seconds'] // 60
        total_secs = stats['total_duration_seconds'] % 60
        hours = total_mins // 60
        mins = total_mins % 60
        stats['total_duration_formatted'] = f"{hours}h {mins}m {total_secs}s"
        
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


def main():
    """Demo usage"""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage: python suno_downloader.py <json_file> [download_dir]")
        print("\nExample: python suno_downloader.py suno_songs/suno_liked_songs_20251031.json")
        sys.exit(1)
    
    json_path = sys.argv[1]
    download_dir = sys.argv[2] if len(sys.argv) > 2 else "suno_downloads"
    
    # Initialize components
    downloader = SunoDownloader(download_dir)
    playlist_mgr = PlaylistManager()
    analyzer = CollectionAnalyzer(json_path)
    
    # Show statistics
    print("\n📊 Collection Statistics:")
    stats = analyzer.get_statistics()
    print(f"  Total songs: {stats['total_songs']}")
    print(f"  Total duration: {stats['total_duration_formatted']}")
    print(f"  Songs with lyrics: {stats['with_lyrics']}")
    print(f"  Tags: {list(stats['tags_distribution'].keys())[:5]}...")
    
    # Download all
    print(f"\n📥 Downloading to: {download_dir}/")
    results = downloader.download_from_json(json_path)
    
    # Create playlist
    if results['success']:
        playlist_mgr.create_m3u(
            [r['song'] for r in results['success']], 
            "suno_collection",
            download_dir
        )


if __name__ == "__main__":
    main()
