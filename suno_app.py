#!/usr/bin/env python3
"""
Suno Extractor App - Interactive extraction and download tool
Extracts liked songs from Suno and downloads them as WAV files
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from suno_extractor import SunoExtractor
from suno_downloader import SunoDownloader


def clear_screen():
    """Clear terminal screen"""
    print("\033[2J\033[H", end="")


def print_header():
    """Print app header"""
    print("=" * 60)
    print("  SUNO EXTRACTOR - Liked Songs Downloader (WAV)")
    print("=" * 60)
    print()


def get_song_limit_choice():
    """Get user choice for number of songs to process"""
    print("How many liked songs do you want to process?")
    print()
    print("  [1] 50 songs")
    print("  [2] 100 songs")
    print("  [3] 200 songs")
    print("  [4] 500 songs")
    print("  [5] ALL songs")
    print()
    
    while True:
        choice = input("Enter choice (1-5): ").strip()
        if choice == "1":
            return 50
        elif choice == "2":
            return 100
        elif choice == "3":
            return 200
        elif choice == "4":
            return 500
        elif choice == "5":
            return None  # None means all
        else:
            print("Invalid choice. Please enter 1-5.")


def check_chrome_connection(port=9222):
    """Check if Chrome is running with debug port"""
    print(f"Checking Chrome connection on port {port}...")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
        driver = webdriver.Chrome(options=options)
        
        current_url = driver.current_url
        print(f"  Connected! Current URL: {current_url}")
        
        # Check if on Suno
        if "suno.com" not in current_url:
            print("  WARNING: Not on suno.com - navigating to liked songs...")
            driver.get("https://suno.com/me?liked=true")
            time.sleep(3)
            print(f"  Now on: {driver.current_url}")
        
        return True
        
    except Exception as e:
        print(f"  ERROR: Could not connect to Chrome: {e}")
        print()
        print("  Please start Chrome with remote debugging:")
        print('  chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\\ChromeDebugProfile"')
        print()
        return False


def extract_songs(limit=None, port=9222):
    """Extract liked songs from Suno"""
    print()
    print("-" * 60)
    print("STEP 1: Extracting liked songs from Suno...")
    print("-" * 60)
    
    extractor = SunoExtractor(output_dir="suno_songs", browser="chrome")
    
    try:
        extractor.connect_to_existing_browser(debug_port=port)
        
        # Run extraction
        output_files = extractor.run_extraction(
            extract_details=True,  # Get lyrics
            save_formats=['json'],
            tabs=['likes'],
            exclude_disliked=True
        )
        
        json_path = output_files.get('json')
        if not json_path:
            print("ERROR: No JSON output generated")
            return None
        
        # Load and optionally limit songs
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        total_songs = len(data['songs'])
        print(f"  Extracted {total_songs} songs total")
        
        if limit and limit < total_songs:
            data['songs'] = data['songs'][:limit]
            data['metadata']['total_songs'] = len(data['songs'])
            
            # Save limited version
            limited_path = Path(json_path).parent / f"suno_liked_limited_{limit}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(limited_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"  Limited to {limit} songs")
            return str(limited_path)
        
        return str(json_path)
        
    except Exception as e:
        print(f"ERROR during extraction: {e}")
        return None


def download_songs(json_path, format='wav'):
    """Download songs as WAV files"""
    print()
    print("-" * 60)
    print(f"STEP 2: Downloading songs as {format.upper()}...")
    print("-" * 60)
    
    downloader = SunoDownloader("suno_downloads")
    
    try:
        results = downloader.download_from_json(json_path, format)
        
        success = len(results.get('success', []))
        failed = len(results.get('failed', []))
        
        print()
        print(f"  SUCCESS: {success} songs downloaded")
        print(f"  FAILED:  {failed} songs")
        
        return success, failed
        
    except Exception as e:
        print(f"ERROR during download: {e}")
        return 0, 0


def generate_reports(json_path):
    """Generate grouping reports"""
    print()
    print("-" * 60)
    print("STEP 3: Generating grouping reports...")
    print("-" * 60)
    
    try:
        from suno_grouping import _load_songs, group_by_title, group_by_lyrics, write_title_report, write_lyrics_report
        
        songs = _load_songs(Path(json_path))
        output_dir = Path("suno_groups")
        output_dir.mkdir(exist_ok=True)
        
        title_groups = group_by_title(songs)
        lyrics_groups = group_by_lyrics(songs)
        
        write_title_report(title_groups, output_dir / "group_by_title.md")
        write_lyrics_report(lyrics_groups, output_dir / "group_by_lyrics.md")
        
        print(f"  Title groups: {len(title_groups)}")
        print(f"  Lyrics groups: {len(lyrics_groups)}")
        print(f"  Reports saved to: {output_dir}")
        
    except Exception as e:
        print(f"ERROR generating reports: {e}")


def main():
    """Main app entry point"""
    clear_screen()
    print_header()
    
    # Check Chrome connection first
    if not check_chrome_connection():
        print()
        input("Press Enter to exit...")
        sys.exit(1)
    
    print()
    
    # Get user choice for song limit
    limit = get_song_limit_choice()
    limit_str = str(limit) if limit else "ALL"
    
    print()
    print(f"Processing {limit_str} liked songs...")
    print()
    
    # Confirm
    confirm = input("Start extraction and download? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        sys.exit(0)
    
    # Extract songs
    json_path = extract_songs(limit=limit)
    if not json_path:
        print()
        print("Extraction failed. Exiting.")
        input("Press Enter to exit...")
        sys.exit(1)
    
    # Download as WAV
    success, failed = download_songs(json_path, format='wav')
    
    # Generate reports
    generate_reports(json_path)
    
    # Summary
    print()
    print("=" * 60)
    print("  COMPLETE!")
    print("=" * 60)
    print(f"  Songs extracted: {json_path}")
    print(f"  Downloads: {success} success, {failed} failed")
    print(f"  Reports: suno_groups/")
    print()
    
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
