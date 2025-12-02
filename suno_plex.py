#!/usr/bin/env python3
"""
Suno Plex Integration - Add Suno songs to Plex Media Server
Organizes music library for Plex compatibility
"""

import os
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Shared utilities
from suno_utils import safe_filename

logger = logging.getLogger(__name__)

# PlexAPI import
try:
    from plexapi.server import PlexServer
    from plexapi.myplex import MyPlexAccount
    PLEX_AVAILABLE = True
except ImportError:
    PLEX_AVAILABLE = False
    logger.warning("plexapi not installed. Run: pip install plexapi")


class PlexMusicOrganizer:
    """
    Organize Suno songs for Plex Music library compatibility
    
    Plex expects music organized as:
    /Music/Artist/Album/Track.mp3
    """
    
    def __init__(self, source_dir: str = "suno_downloads",
                 plex_music_dir: str = "plex_music"):
        self.source_dir = Path(source_dir)
        self.plex_music_dir = Path(plex_music_dir)
        self.plex_music_dir.mkdir(parents=True, exist_ok=True)
    
    def organize_for_plex(self, songs: List[Dict] = None,
                          artist_name: str = "Suno AI",
                          album_name: str = None) -> int:
        """
        Organize songs into Plex-compatible folder structure
        
        Args:
            songs: List of song dictionaries (uses all files if None)
            artist_name: Default artist name
            album_name: Album name (uses date if None)
            
        Returns:
            Number of files organized
        """
        if album_name is None:
            album_name = f"Suno Collection {datetime.now().strftime('%Y-%m')}"
        
        # Create folder structure
        artist_dir = self.plex_music_dir / safe_filename(artist_name)
        album_dir = artist_dir / safe_filename(album_name)
        album_dir.mkdir(parents=True, exist_ok=True)
        
        count = 0
        
        if songs:
            # Organize from song list
            for i, song in enumerate(songs, 1):
                src_path = self._find_audio_file(song)
                if not src_path:
                    continue
                
                # Create track filename with number
                title = song.get('title', f'Track {i}')
                ext = src_path.suffix
                track_name = f"{i:02d} - {safe_filename(title)}{ext}"
                
                dest_path = album_dir / track_name
                
                # Copy file
                shutil.copy2(src_path, dest_path)
                
                # Copy cover art if available
                self._copy_cover_art(song, album_dir)
                
                count += 1
                logger.info(f"Organized: {track_name}")
        else:
            # Organize all files from source directory
            for i, src_path in enumerate(sorted(self.source_dir.glob('*.mp3')), 1):
                track_name = f"{i:02d} - {src_path.stem}{src_path.suffix}"
                dest_path = album_dir / track_name
                
                shutil.copy2(src_path, dest_path)
                count += 1
        
        logger.info(f"Organized {count} tracks to: {album_dir}")
        return count
    
    def organize_by_genre(self, songs: List[Dict],
                          artist_name: str = "Suno AI") -> Dict[str, int]:
        """
        Organize songs into albums by genre/tag
        
        Returns:
            Dict mapping genre to track count
        """
        genres = {}
        
        for song in songs:
            # Get primary tag as genre
            tags = song.get('tags', [])
            genre = tags[0] if tags else 'Uncategorized'
            
            if genre not in genres:
                genres[genre] = []
            genres[genre].append(song)
        
        results = {}
        
        for genre, genre_songs in genres.items():
            album_name = f"Suno {genre.title()}"
            count = self.organize_for_plex(
                genre_songs,
                artist_name=artist_name,
                album_name=album_name
            )
            results[genre] = count
        
        return results
    
    def organize_by_month(self, songs: List[Dict],
                          artist_name: str = "Suno AI") -> Dict[str, int]:
        """Organize songs into albums by creation month"""
        months = {}
        
        for song in songs:
            created = song.get('created_at', '')
            if created:
                try:
                    month = created[:7]  # YYYY-MM
                except Exception:
                    month = 'Unknown'
            else:
                month = 'Unknown'
            
            if month not in months:
                months[month] = []
            months[month].append(song)
        
        results = {}
        
        for month, month_songs in months.items():
            album_name = f"Suno {month}"
            count = self.organize_for_plex(
                month_songs,
                artist_name=artist_name,
                album_name=album_name
            )
            results[month] = count
        
        return results
    
    def _find_audio_file(self, song: Dict) -> Optional[Path]:
        """Find audio file for a song"""
        # Try local_audio_path first
        if song.get('local_audio_path'):
            path = Path(song['local_audio_path'])
            if path.exists():
                return path
        
        # Try to find by title
        title = song.get('title', '')
        if title:
            safe_title = safe_filename(title)
            for ext in ['.mp3', '.m4a', '.wav']:
                path = self.source_dir / f"{safe_title}{ext}"
                if path.exists():
                    return path
        
        # Try by ID
        song_id = song.get('id', '')
        if song_id:
            for ext in ['.mp3', '.m4a', '.wav']:
                path = self.source_dir / f"{song_id}{ext}"
                if path.exists():
                    return path
        
        return None
    
    def _copy_cover_art(self, song: Dict, album_dir: Path):
        """Copy cover art to album folder"""
        cover_names = ['cover.jpg', 'cover.png', 'folder.jpg', 'album.jpg']
        
        # Check if cover already exists
        for name in cover_names:
            if (album_dir / name).exists():
                return
        
        # Try to find cover art
        cover_path = song.get('local_cover_path')
        if cover_path and Path(cover_path).exists():
            dest = album_dir / 'cover.jpg'
            shutil.copy2(cover_path, dest)
    

class PlexServerIntegration:
    """
    Direct integration with Plex Media Server
    Requires Plex server URL and token
    """
    
    def __init__(self, server_url: str = None, token: str = None):
        """
        Initialize Plex connection
        
        Args:
            server_url: Plex server URL (e.g., http://localhost:32400)
            token: Plex authentication token
        """
        self.server_url = server_url or os.environ.get('PLEX_URL')
        self.token = token or os.environ.get('PLEX_TOKEN')
        self.server = None
        
        if PLEX_AVAILABLE and self.server_url and self.token:
            try:
                self.server = PlexServer(self.server_url, self.token)
                logger.info(f"Connected to Plex: {self.server.friendlyName}")
            except Exception as e:
                logger.error(f"Failed to connect to Plex: {e}")
    
    def get_music_libraries(self) -> List[str]:
        """Get available music libraries"""
        if not self.server:
            return []
        
        return [
            section.title
            for section in self.server.library.sections()
            if section.type == 'artist'
        ]
    
    def refresh_library(self, library_name: str = None):
        """
        Trigger library refresh
        
        Args:
            library_name: Name of music library to refresh (refreshes all if None)
        """
        if not self.server:
            logger.warning("Not connected to Plex")
            return
        
        try:
            if library_name:
                section = self.server.library.section(library_name)
                section.refresh()
                logger.info(f"Refreshing library: {library_name}")
            else:
                # Refresh all music libraries
                for section in self.server.library.sections():
                    if section.type == 'artist':
                        section.refresh()
                        logger.info(f"Refreshing library: {section.title}")
        except Exception as e:
            logger.error(f"Failed to refresh library: {e}")
    
    def search_songs(self, query: str, library_name: str = None) -> List[Dict]:
        """Search for songs in Plex library"""
        if not self.server:
            return []
        
        results = []
        
        try:
            if library_name:
                sections = [self.server.library.section(library_name)]
            else:
                sections = [s for s in self.server.library.sections() if s.type == 'artist']
            
            for section in sections:
                tracks = section.searchTracks(title=query)
                for track in tracks:
                    results.append({
                        'title': track.title,
                        'artist': track.artist().title if track.artist() else '',
                        'album': track.album().title if track.album() else '',
                        'duration': track.duration,
                        'rating': track.userRating,
                        'key': track.key
                    })
        except Exception as e:
            logger.error(f"Search failed: {e}")
        
        return results
    
    def get_recently_added(self, library_name: str = None, limit: int = 20) -> List[Dict]:
        """Get recently added tracks"""
        if not self.server:
            return []
        
        results = []
        
        try:
            if library_name:
                section = self.server.library.section(library_name)
                tracks = section.recentlyAdded()[:limit]
            else:
                tracks = self.server.library.recentlyAdded()[:limit]
            
            for item in tracks:
                if item.type == 'track':
                    results.append({
                        'title': item.title,
                        'artist': item.artist().title if hasattr(item, 'artist') else '',
                        'added_at': str(item.addedAt)
                    })
        except Exception as e:
            logger.error(f"Failed to get recent: {e}")
        
        return results
    
    def create_playlist(self, name: str, track_keys: List[str]) -> bool:
        """
        Create a playlist in Plex
        
        Args:
            name: Playlist name
            track_keys: List of track keys (from search results)
        """
        if not self.server:
            return False
        
        try:
            items = [self.server.fetchItem(key) for key in track_keys]
            playlist = self.server.createPlaylist(name, items=items)
            logger.info(f"Created playlist: {name} with {len(items)} tracks")
            return True
        except Exception as e:
            logger.error(f"Failed to create playlist: {e}")
            return False


def export_to_plex(db=None, source_dir: str = "suno_downloads",
                   plex_dir: str = "plex_music",
                   organize_by: str = "album") -> int:
    """
    Quick export function to organize songs for Plex
    
    Args:
        db: Database instance
        source_dir: Source audio directory
        plex_dir: Destination Plex music directory
        organize_by: "album", "genre", or "month"
        
    Returns:
        Number of tracks exported
    """
    organizer = PlexMusicOrganizer(source_dir, plex_dir)
    
    songs = []
    if db:
        songs = db.get_all_songs()
    
    if organize_by == "genre":
        results = organizer.organize_by_genre(songs)
        return sum(results.values())
    elif organize_by == "month":
        results = organizer.organize_by_month(songs)
        return sum(results.values())
    else:
        return organizer.organize_for_plex(songs)


def main():
    import argparse
    
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(description="Suno Plex Integration")
    parser.add_argument('command', choices=['organize', 'refresh', 'search', 'recent'])
    parser.add_argument('--source', default='suno_downloads', help='Source directory')
    parser.add_argument('--dest', default='plex_music', help='Plex music directory')
    parser.add_argument('--organize-by', choices=['album', 'genre', 'month'], default='album')
    parser.add_argument('--plex-url', help='Plex server URL')
    parser.add_argument('--plex-token', help='Plex token')
    parser.add_argument('--library', help='Plex library name')
    parser.add_argument('--query', help='Search query')
    
    args = parser.parse_args()
    
    if args.command == 'organize':
        organizer = PlexMusicOrganizer(args.source, args.dest)
        
        # Try to get songs from database
        try:
            from suno_core import get_database
            db = get_database()
            songs = db.get_all_songs()
        except Exception:
            songs = None
        
        if args.organize_by == 'genre':
            results = organizer.organize_by_genre(songs or [])
            print(f"Organized by genre: {results}")
        elif args.organize_by == 'month':
            results = organizer.organize_by_month(songs or [])
            print(f"Organized by month: {results}")
        else:
            count = organizer.organize_for_plex(songs)
            print(f"Organized {count} tracks")
    
    elif args.command in ['refresh', 'search', 'recent']:
        if not PLEX_AVAILABLE:
            print("plexapi not installed. Run: pip install plexapi")
            return
        
        plex = PlexServerIntegration(args.plex_url, args.plex_token)
        
        if not plex.server:
            print("Could not connect to Plex server")
            return
        
        if args.command == 'refresh':
            plex.refresh_library(args.library)
            print("Library refresh triggered")
        
        elif args.command == 'search' and args.query:
            results = plex.search_songs(args.query, args.library)
            for r in results:
                print(f"  {r['artist']} - {r['title']}")
        
        elif args.command == 'recent':
            results = plex.get_recently_added(args.library)
            for r in results:
                print(f"  {r['title']} (added: {r['added_at']})")


if __name__ == "__main__":
    main()
