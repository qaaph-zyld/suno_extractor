#!/usr/bin/env python3
"""
Suno Music Player - Local audio playback with controls
Supports playing downloaded Suno songs with a rich terminal UI
"""

import json
import os
import sys
import time
import threading
from pathlib import Path
from typing import List, Dict, Optional
import random

# Shared utilities
from suno_utils import safe_filename, parse_duration

# Audio playback libraries
try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# Fallback to VLC if available
try:
    import vlc
    VLC_AVAILABLE = True
except ImportError:
    VLC_AVAILABLE = False

# Rich terminal UI
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
    from rich.live import Live
    from rich.layout import Layout
    from rich.text import Text
    from rich.prompt import Prompt
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

console = Console() if RICH_AVAILABLE else None


class AudioBackend:
    """Abstract audio backend interface"""
    
    def load(self, filepath: str) -> bool:
        raise NotImplementedError
    
    def play(self):
        raise NotImplementedError
    
    def pause(self):
        raise NotImplementedError
    
    def resume(self):
        raise NotImplementedError
    
    def stop(self):
        raise NotImplementedError
    
    def set_volume(self, volume: float):
        raise NotImplementedError
    
    def get_position(self) -> float:
        raise NotImplementedError
    
    def get_duration(self) -> float:
        raise NotImplementedError
    
    def is_playing(self) -> bool:
        raise NotImplementedError
    
    def seek(self, position: float):
        raise NotImplementedError


class PygameBackend(AudioBackend):
    """Pygame-based audio backend"""
    
    def __init__(self):
        if not PYGAME_AVAILABLE:
            raise RuntimeError("Pygame not available")
        self.current_file = None
        self._duration = 0
        
    def load(self, filepath: str) -> bool:
        try:
            pygame.mixer.music.load(filepath)
            self.current_file = filepath
            # Estimate duration from file size (rough estimate)
            # Pygame doesn't provide duration directly for all formats
            self._duration = self._estimate_duration(filepath)
            return True
        except Exception as e:
            print(f"Failed to load: {e}")
            return False
    
    def _estimate_duration(self, filepath: str) -> float:
        """Estimate duration from file metadata or size"""
        try:
            from mutagen.mp3 import MP3
            audio = MP3(filepath)
            return audio.info.length
        except Exception:
            pass
        
        try:
            from mutagen.mp4 import MP4
            audio = MP4(filepath)
            return audio.info.length
        except Exception:
            pass
        
        # Fallback: estimate from file size (assuming ~128kbps)
        try:
            size = os.path.getsize(filepath)
            return size / (128 * 1024 / 8)  # bytes to seconds at 128kbps
        except Exception:
            return 180  # Default 3 minutes
    
    def play(self):
        pygame.mixer.music.play()
    
    def pause(self):
        pygame.mixer.music.pause()
    
    def resume(self):
        pygame.mixer.music.unpause()
    
    def stop(self):
        pygame.mixer.music.stop()
    
    def set_volume(self, volume: float):
        pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
    
    def get_position(self) -> float:
        return pygame.mixer.music.get_pos() / 1000.0
    
    def get_duration(self) -> float:
        return self._duration
    
    def is_playing(self) -> bool:
        return pygame.mixer.music.get_busy()
    
    def seek(self, position: float):
        pygame.mixer.music.set_pos(position)


class VLCBackend(AudioBackend):
    """VLC-based audio backend"""
    
    def __init__(self):
        if not VLC_AVAILABLE:
            raise RuntimeError("VLC not available")
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.media = None
        
    def load(self, filepath: str) -> bool:
        try:
            self.media = self.instance.media_new(filepath)
            self.player.set_media(self.media)
            return True
        except Exception as e:
            print(f"Failed to load: {e}")
            return False
    
    def play(self):
        self.player.play()
    
    def pause(self):
        self.player.pause()
    
    def resume(self):
        self.player.play()
    
    def stop(self):
        self.player.stop()
    
    def set_volume(self, volume: float):
        self.player.audio_set_volume(int(volume * 100))
    
    def get_position(self) -> float:
        return self.player.get_time() / 1000.0
    
    def get_duration(self) -> float:
        length = self.player.get_length()
        return length / 1000.0 if length > 0 else 0
    
    def is_playing(self) -> bool:
        return self.player.is_playing()
    
    def seek(self, position: float):
        self.player.set_time(int(position * 1000))


class SunoPlayer:
    """Main music player for Suno songs"""
    
    def __init__(self, audio_dir: str = "suno_downloads"):
        self.audio_dir = Path(audio_dir)
        self.playlist: List[Dict] = []
        self.current_index = 0
        self.volume = 0.7
        self.shuffle = False
        self.repeat = False  # False, 'one', 'all'
        self.is_paused = False
        
        # Initialize audio backend
        self.backend = self._init_backend()
        if self.backend:
            self.backend.set_volume(self.volume)
    
    def _init_backend(self) -> Optional[AudioBackend]:
        """Initialize the best available audio backend"""
        if PYGAME_AVAILABLE:
            try:
                return PygameBackend()
            except Exception as e:
                print(f"Pygame init failed: {e}")
        
        if VLC_AVAILABLE:
            try:
                return VLCBackend()
            except Exception as e:
                print(f"VLC init failed: {e}")
        
        print("No audio backend available. Install pygame or python-vlc.")
        return None
    
    def load_playlist_from_json(self, json_path: str) -> int:
        """Load playlist from extraction JSON"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        songs = data.get('songs', [])
        
        # Match songs to local files
        for song in songs:
            title = song.get('title', '')
            safe_title = safe_filename(title)
            
            # Check for audio file
            for ext in ['.mp3', '.m4a', '.wav']:
                filepath = self.audio_dir / f"{safe_title}{ext}"
                if filepath.exists():
                    song['local_path'] = str(filepath)
                    self.playlist.append(song)
                    break
        
        return len(self.playlist)
    
    def load_playlist_from_dir(self) -> int:
        """Load all audio files from directory"""
        self.playlist = []
        
        for ext in ['*.mp3', '*.m4a', '*.wav', '*.ogg', '*.flac']:
            for filepath in self.audio_dir.glob(ext):
                song = {
                    'title': filepath.stem,
                    'local_path': str(filepath),
                    'duration': '',
                    'tags': []
                }
                self.playlist.append(song)
        
        return len(self.playlist)
    
    def play(self, index: int = None):
        """Play a song by index"""
        if not self.backend or not self.playlist:
            return False
        
        if index is not None:
            self.current_index = index % len(self.playlist)
        
        song = self.playlist[self.current_index]
        filepath = song.get('local_path')
        
        if not filepath or not Path(filepath).exists():
            print(f"File not found: {filepath}")
            return False
        
        if self.backend.load(filepath):
            self.backend.play()
            self.is_paused = False
            return True
        
        return False
    
    def pause(self):
        """Pause playback"""
        if self.backend:
            self.backend.pause()
            self.is_paused = True
    
    def resume(self):
        """Resume playback"""
        if self.backend:
            self.backend.resume()
            self.is_paused = False
    
    def toggle_pause(self):
        """Toggle pause state"""
        if self.is_paused:
            self.resume()
        else:
            self.pause()
    
    def stop(self):
        """Stop playback"""
        if self.backend:
            self.backend.stop()
            self.is_paused = False
    
    def next(self):
        """Play next song"""
        if self.shuffle:
            self.current_index = random.randint(0, len(self.playlist) - 1)
        else:
            self.current_index = (self.current_index + 1) % len(self.playlist)
        self.play()
    
    def previous(self):
        """Play previous song"""
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self.play()
    
    def set_volume(self, volume: float):
        """Set volume (0.0 to 1.0)"""
        self.volume = max(0.0, min(1.0, volume))
        if self.backend:
            self.backend.set_volume(self.volume)
    
    def volume_up(self, step: float = 0.1):
        """Increase volume"""
        self.set_volume(self.volume + step)
    
    def volume_down(self, step: float = 0.1):
        """Decrease volume"""
        self.set_volume(self.volume - step)
    
    def toggle_shuffle(self):
        """Toggle shuffle mode"""
        self.shuffle = not self.shuffle
    
    def toggle_repeat(self):
        """Cycle repeat mode: off -> one -> all -> off"""
        if self.repeat == False:
            self.repeat = 'one'
        elif self.repeat == 'one':
            self.repeat = 'all'
        else:
            self.repeat = False
    
    def get_current_song(self) -> Optional[Dict]:
        """Get currently playing song"""
        if self.playlist and 0 <= self.current_index < len(self.playlist):
            return self.playlist[self.current_index]
        return None
    
    def get_progress(self) -> tuple:
        """Get playback progress (position, duration)"""
        if self.backend:
            return self.backend.get_position(), self.backend.get_duration()
        return 0, 0
    
    def is_playing(self) -> bool:
        """Check if currently playing"""
        if self.backend:
            return self.backend.is_playing()
        return False
    
    def format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS"""
        if seconds < 0:
            seconds = 0
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"


class PlayerUI:
    """Rich terminal UI for the player"""
    
    def __init__(self, player: SunoPlayer):
        self.player = player
        self.running = False
    
    def run(self):
        """Run interactive player UI"""
        if not RICH_AVAILABLE:
            print("Rich library required for UI. Install with: pip install rich")
            return
        
        self.running = True
        
        console.print(Panel.fit(
            "[bold cyan]🎵 SUNO MUSIC PLAYER[/bold cyan]\n"
            "Press keys to control playback",
            border_style="cyan"
        ))
        
        self.show_help()
        
        # Main loop
        while self.running:
            self.render_now_playing()
            self.handle_input()
    
    def show_help(self):
        """Show keyboard controls"""
        help_text = """
[bold]Controls:[/bold]
  [cyan]SPACE[/cyan]  Play/Pause    [cyan]N[/cyan]  Next      [cyan]P[/cyan]  Previous
  [cyan]+/-[/cyan]    Volume        [cyan]S[/cyan]  Shuffle   [cyan]R[/cyan]  Repeat
  [cyan]L[/cyan]      Show playlist [cyan]Q[/cyan]  Quit
        """
        console.print(help_text)
    
    def render_now_playing(self):
        """Render current song info"""
        song = self.player.get_current_song()
        if not song:
            console.print("[dim]No song loaded[/dim]")
            return
        
        pos, dur = self.player.get_progress()
        
        # Status indicators
        status = "▶" if self.player.is_playing() else "⏸" if self.player.is_paused else "⏹"
        shuffle_icon = "🔀" if self.player.shuffle else ""
        repeat_icon = "🔁" if self.player.repeat == 'all' else "🔂" if self.player.repeat == 'one' else ""
        
        # Progress bar
        progress_pct = (pos / dur * 100) if dur > 0 else 0
        bar_width = 40
        filled = int(bar_width * progress_pct / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        console.print(f"\r{status} [bold cyan]{song.get('title', 'Unknown')}[/bold cyan]")
        console.print(f"   {self.player.format_time(pos)} [{bar}] {self.player.format_time(dur)}")
        console.print(f"   Vol: {int(self.player.volume * 100)}% {shuffle_icon} {repeat_icon}")
    
    def handle_input(self):
        """Handle keyboard input"""
        try:
            # Simple input handling
            cmd = input("\n> ").strip().lower()
            
            if cmd in ('q', 'quit', 'exit'):
                self.player.stop()
                self.running = False
            elif cmd in ('', ' ', 'space'):
                self.player.toggle_pause()
            elif cmd in ('n', 'next'):
                self.player.next()
            elif cmd in ('p', 'prev', 'previous'):
                self.player.previous()
            elif cmd in ('+', 'up'):
                self.player.volume_up()
                console.print(f"Volume: {int(self.player.volume * 100)}%")
            elif cmd in ('-', 'down'):
                self.player.volume_down()
                console.print(f"Volume: {int(self.player.volume * 100)}%")
            elif cmd in ('s', 'shuffle'):
                self.player.toggle_shuffle()
                console.print(f"Shuffle: {'ON' if self.player.shuffle else 'OFF'}")
            elif cmd in ('r', 'repeat'):
                self.player.toggle_repeat()
                console.print(f"Repeat: {self.player.repeat or 'OFF'}")
            elif cmd in ('l', 'list'):
                self.show_playlist()
            elif cmd.isdigit():
                self.player.play(int(cmd) - 1)
            elif cmd in ('h', 'help', '?'):
                self.show_help()
                
        except KeyboardInterrupt:
            self.running = False
            self.player.stop()
    
    def show_playlist(self):
        """Display playlist"""
        table = Table(title="Playlist")
        table.add_column("#", style="dim", width=4)
        table.add_column("Title", min_width=30)
        table.add_column("Duration", width=8)
        table.add_column("", width=3)
        
        for i, song in enumerate(self.player.playlist):
            marker = "▶" if i == self.player.current_index else ""
            style = "bold cyan" if i == self.player.current_index else ""
            
            table.add_row(
                str(i + 1),
                song.get('title', 'Unknown')[:40],
                song.get('duration', '-'),
                marker,
                style=style
            )
        
        console.print(table)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Suno Music Player")
    parser.add_argument('--dir', default='suno_downloads', help='Audio directory')
    parser.add_argument('--json', help='Load playlist from extraction JSON')
    parser.add_argument('--play', type=int, help='Start playing at index')
    
    args = parser.parse_args()
    
    # Initialize player
    player = SunoPlayer(args.dir)
    
    if not player.backend:
        print("No audio backend available. Install pygame or python-vlc.")
        sys.exit(1)
    
    # Load playlist
    if args.json:
        count = player.load_playlist_from_json(args.json)
        print(f"Loaded {count} songs from JSON")
    else:
        count = player.load_playlist_from_dir()
        print(f"Found {count} audio files")
    
    if not player.playlist:
        print("No songs found!")
        sys.exit(1)
    
    # Start playback
    if args.play is not None:
        player.play(args.play - 1)
    
    # Run UI
    ui = PlayerUI(player)
    ui.run()


if __name__ == "__main__":
    main()
