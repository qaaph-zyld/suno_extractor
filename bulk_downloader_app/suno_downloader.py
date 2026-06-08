#!/usr/bin/env python3
"""
Suno Library Bulk Downloader
=============================
Automated script to bulk download your entire Suno music library.

Requirements:
    pip install requests tqdm

Usage:
    1. Get your Bearer token from Suno:
       - Login to suno.com in your browser
       - Open DevTools (F12) -> Network tab
       - Filter by 'feed' or 'clips'
       - Click any request to studio-api.prod.suno.com
       - In Headers, find 'Authorization: Bearer eyJ...'
       - Copy the token value (everything after 'Bearer ')
    
    2. Run script:
       python suno_downloader.py
    
    3. Paste the Bearer token when prompted

Features:
    - Automatic pagination through entire library
    - Parallel downloads with connection pooling
    - Resume capability for interrupted downloads
    - Comprehensive error handling and retry logic
    - Progress bars for tracking
    - Organized output by date
"""

import os
import json
import base64
import time
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple

try:
    import requests
    from tqdm import tqdm
except ImportError:
    print("Error: Required packages not installed.")
    print("Install with: pip install requests tqdm")
    sys.exit(1)


class SunoDownloader:
    """Main downloader class for Suno library management."""
    
    BASE_URL = "https://studio-api.prod.suno.com"
    CLIPS_ENDPOINT = "/api/feed/v3"
    
    def __init__(self, token: str, output_dir: str = "suno_library", convert_to_wav: bool = True):
        """
        Initialize downloader with Bearer token.
        
        Args:
            token: Bearer token from Suno API (from Authorization header)
            output_dir: Directory to save downloaded files
        """
        self.token = token
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.convert_to_wav = convert_to_wav
        
        # Configure session with connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Authorization': f'Bearer {token}'
        })
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 2
        
        # Download statistics
        self.stats = {
            'total': 0,
            'downloaded': 0,
            'skipped': 0,
            'failed': 0
        }
    
    def _make_browser_token(self) -> str:
        """Generate a browser-token payload similar to the web client."""
        payload = json.dumps({"timestamp": int(time.time() * 1000)})
        encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
        return json.dumps({"token": encoded})
    
    def fetch_clips(self, cursor: Optional[str] = None, limit: int = 20) -> Tuple[List[Dict], Optional[str]]:
        """
        Fetch clips from Suno API with cursor-based pagination.
        
        Args:
            cursor: Opaque cursor string from previous response (None for first page)
            limit: Number of clips to request per page
        
        Returns:
            Tuple of (clips list, next_cursor string or None)
        """
        url = f"{self.BASE_URL}{self.CLIPS_ENDPOINT}"
        payload = {
            "cursor": cursor,
            "limit": limit,
            "filters": {
                "liked": "True",
                "disliked": "False",
                "trashed": "False",
                "fromStudioProject": {"presence": "False"},
                "stem": {"presence": "False"},
                "workspace": {"presence": "True", "workspaceId": "default"},
            },
        }
        
        for attempt in range(self.max_retries):
            try:
                headers = self.session.headers.copy()
                headers['browser-token'] = self._make_browser_token()
                response = self.session.post(url, json=payload, headers=headers, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                clips = data.get('clips', [])

                # Cursor-based pagination: if API returns a new cursor, we have more pages
                next_cursor = (
                    data.get('cursor')
                    or data.get('next_cursor')
                    or data.get('nextCursor')
                )

                return clips, next_cursor
                
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    print(f"\n⚠ Retry {attempt + 1}/{self.max_retries} for page: {e}")
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    print(f"\n✗ Failed to fetch page: {e}")
                    return [], None
        
        return [], None
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename by removing invalid characters.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename safe for filesystem
        """
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip()
    
    def download_file(self, url: str, filepath: Path) -> bool:
        """
        Download a single file with resume capability.
        
        Args:
            url: Direct download URL
            filepath: Destination file path
            
        Returns:
            True if successful, False otherwise
        """
        # Check if file already exists and is complete
        if filepath.exists():
            try:
                # Verify file size matches
                response = self.session.head(url, timeout=10)
                remote_size = int(response.headers.get('content-length', 0))
                local_size = filepath.stat().st_size
                
                if remote_size > 0 and local_size == remote_size:
                    return True  # File already downloaded
            except Exception:
                pass  # Continue with download attempt
        
        # Download with retry logic
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, stream=True, timeout=60)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                
                # Write file with progress tracking
                filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(filepath, 'wb') as f:
                    if total_size == 0:
                        f.write(response.content)
                    else:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                
                return True
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    print(f"\n✗ Failed to download {filepath.name}: {e}")
                    # Clean up partial download
                    if filepath.exists():
                        filepath.unlink()
                    return False
        
        return False
    
    def convert_audio_to_wav(self, audio_path: Path) -> None:
        if not self.convert_to_wav:
            return
        try:
            if shutil.which("ffmpeg") is None:
                return
            wav_path = audio_path.with_suffix('.wav')
            if wav_path.exists():
                return
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(audio_path), str(wav_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
        except Exception:
            # Conversion failures should not fail the whole download
            pass
    
    def process_clip(self, clip: Dict) -> Optional[Dict]:
        """
        Extract download information from clip metadata.
        
        Args:
            clip: Clip metadata dictionary
            
        Returns:
            Dictionary with download info or None if invalid
        """
        clip_id = clip.get('id')
        title = clip.get('title', 'Untitled')
        audio_url = clip.get('audio_url')
        video_url = clip.get('video_url')
        image_url = clip.get('image_large_url') or clip.get('image_url')
        created_at = clip.get('created_at', '')
        
        # Skip clips without audio
        if not audio_url or not clip_id:
            return None
        
        # Parse date for organization
        try:
            date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            date_folder = date_obj.strftime('%Y-%m-%d')
        except Exception:
            date_folder = 'unknown_date'
        
        # Sanitize title for filename
        safe_title = self.sanitize_filename(title)
        base_filename = f"{clip_id}_{safe_title}"
        
        return {
            'clip_id': clip_id,
            'title': title,
            'date_folder': date_folder,
            'base_filename': base_filename,
            'audio_url': audio_url,
            'video_url': video_url,
            'image_url': image_url,
            'metadata': clip
        }
    
    def download_clip_files(self, clip_info: Dict) -> bool:
        """
        Download all files associated with a clip.
        
        Args:
            clip_info: Processed clip information
            
        Returns:
            True if at least audio was downloaded successfully
        """
        date_folder = self.output_dir / clip_info['date_folder']
        base_filename = clip_info['base_filename']
        
        success = False
        
        # Download audio (required)
        if clip_info['audio_url']:
            audio_ext = Path(clip_info['audio_url']).suffix or '.mp3'
            audio_path = date_folder / f"{base_filename}{audio_ext}"
            if self.download_file(clip_info['audio_url'], audio_path):
                success = True
            if audio_path.exists():
                self.convert_audio_to_wav(audio_path)
        
        # Download video (optional)
        if clip_info['video_url']:
            video_ext = Path(clip_info['video_url']).suffix or '.mp4'
            video_path = date_folder / f"{base_filename}{video_ext}"
            self.download_file(clip_info['video_url'], video_path)
        
        # Download cover image (optional)
        if clip_info['image_url']:
            image_ext = Path(clip_info['image_url']).suffix or '.jpg'
            image_path = date_folder / f"{base_filename}_cover{image_ext}"
            self.download_file(clip_info['image_url'], image_path)
        
        # Save metadata JSON
        metadata_path = date_folder / f"{base_filename}_metadata.json"
        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(clip_info['metadata'], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"\n⚠ Failed to save metadata for {base_filename}: {e}")
        
        return success
    
    def run(self, max_workers: int = 5):
        """
        Main execution method to download entire library.
        
        Args:
            max_workers: Number of parallel download threads
        """
        print("=" * 60)
        print("Suno Library Bulk Downloader")
        print("=" * 60)
        print(f"Output directory: {self.output_dir.absolute()}\n")
        
        # Phase 1: Fetch all clips
        print("📡 Fetching library metadata...")
        all_clips = []
        cursor = None
        
        with tqdm(desc="Fetching pages", unit="page") as pbar:
            while True:
                clips, cursor = self.fetch_clips(cursor)
                if not clips:
                    break
                
                all_clips.extend(clips)
                pbar.update(1)
                pbar.set_postfix({'clips': len(all_clips)})
                
                if not cursor:
                    break
                
                time.sleep(0.5)  # Rate limiting
        
        print(f"\n✓ Found {len(all_clips)} clips in library\n")
        
        # Phase 2: Process clip metadata
        print("📋 Processing clip metadata...")
        download_queue = []
        
        for clip in all_clips:
            clip_info = self.process_clip(clip)
            if clip_info:
                download_queue.append(clip_info)
        
        self.stats['total'] = len(download_queue)
        print(f"✓ {self.stats['total']} clips ready for download\n")
        
        if not download_queue:
            print("⚠ No clips to download. Exiting.")
            return
        
        # Phase 3: Download files in parallel
        print(f"⬇️  Downloading files (using {max_workers} threads)...\n")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all download tasks
            future_to_clip = {
                executor.submit(self.download_clip_files, clip): clip
                for clip in download_queue
            }
            
            # Process completed downloads with progress bar
            with tqdm(total=self.stats['total'], desc="Overall progress", unit="clip") as pbar:
                for future in as_completed(future_to_clip):
                    clip_info = future_to_clip[future]
                    try:
                        success = future.result()
                        if success:
                            self.stats['downloaded'] += 1
                        else:
                            self.stats['failed'] += 1
                    except Exception as e:
                        self.stats['failed'] += 1
                        print(f"\n✗ Error processing {clip_info['title']}: {e}")
                    
                    pbar.update(1)
                    pbar.set_postfix({
                        'OK': self.stats['downloaded'],
                        'Fail': self.stats['failed']
                    })
        
        # Phase 4: Summary
        print("\n" + "=" * 60)
        print("Download Summary")
        print("=" * 60)
        print(f"Total clips:      {self.stats['total']}")
        print(f"✓ Downloaded:     {self.stats['downloaded']}")
        print(f"✗ Failed:         {self.stats['failed']}")
        print(f"\nFiles saved to:   {self.output_dir.absolute()}")
        print("=" * 60)


def get_token_input() -> str:
    """
    Prompt user for Suno Bearer token with instructions.
    
    Returns:
        Bearer token string
    """
    print("\n" + "=" * 60)
    print("Suno Bearer Token Setup")
    print("=" * 60)
    print("\nHow to get your Bearer token:")
    print("1. Login to suno.com in your browser")
    print("2. Press F12 to open Developer Tools")
    print("3. Go to: Network tab, filter by 'feed' or 'clips'")
    print("4. Click any request to studio-api.prod.suno.com")
    print("5. In Headers, find 'Authorization: Bearer eyJ...'")
    print("6. Copy ONLY the token (after 'Bearer ', starts with eyJ)")
    print("=" * 60 + "\n")
    
    token = input("Paste your Bearer token: ").strip()
    
    # Remove 'Bearer ' prefix if user included it
    if token.lower().startswith('bearer '):
        token = token[7:]
    
    if not token:
        print("\n✗ Error: Token cannot be empty")
        sys.exit(1)
    
    return token


def main():
    """Main entry point for script execution."""
    try:
        # Get token from user
        token = get_token_input()
        
        # Initialize and run downloader
        downloader = SunoDownloader(token=token)
        downloader.run(max_workers=5)
        
    except KeyboardInterrupt:
        print("\n\n⚠ Download interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
