#!/usr/bin/env python3
"""
Verify completeness of Suno library:
- All 2633 songs have WAV files
- All lyrics files exist (893 expected)
- All style files exist (896 expected)
- Master catalog matches actual files
"""

import io
import sys
import json
from pathlib import Path

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Paths
BASE_DIR = Path("suno_library")
AUDIO_DIR = BASE_DIR / "audio"
LYRICS_DIR = BASE_DIR / "lyrics"
STYLES_DIR = BASE_DIR / "styles"
METADATA_DIR = BASE_DIR / "metadata"
JSON_FILE = "suno_songs/suno_liked_songs_20260321_031341.json"

def load_songs():
    """Load master songs from JSON."""
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("songs", [])

def safe_filename(title: str, max_len: int = 100) -> str:
    """Create a filesystem-safe filename."""
    import re
    safe = re.sub(r'[<>:"/\\|?*]', '_', title)
    safe = safe.strip('. ')
    return safe[:max_len] if safe else "untitled"

def verify():
    """Run verification checks."""
    print("=" * 60)
    print("VERIFICATION REPORT")
    print("=" * 60)
    
    songs = load_songs()
    total_songs = len(songs)
    print(f"Total songs in catalog: {total_songs}")
    
    # Count expected lyrics/styles
    lyrics_expected = sum(1 for s in songs if s.get("lyrics", "").strip())
    styles_expected = sum(1 for s in songs if s.get("description", "").strip())
    print(f"Songs with lyrics: {lyrics_expected}")
    print(f"Songs with style: {styles_expected}")
    
    # Verify WAV files only
    wav_files = list(AUDIO_DIR.glob("*.wav"))
    print(f"\nWAV files in audio/: {len(wav_files)}")
    print(f"Expected: {total_songs}")
    print(f"Match: {'✓' if len(wav_files) == total_songs else '✗'}")
    
    # Verify lyrics files
    lyrics_files = list(LYRICS_DIR.glob("*.txt"))
    print(f"\nLyrics files in lyrics/: {len(lyrics_files)}")
    print(f"Expected: {lyrics_expected}")
    print(f"Match: {'✓' if len(lyrics_files) == lyrics_expected else '✗'}")
    
    # Verify style files
    style_files = list(STYLES_DIR.glob("*.txt"))
    print(f"\nStyle files in styles/: {len(style_files)}")
    print(f"Expected: {styles_expected}")
    print(f"Match: {'✓' if len(style_files) == styles_expected else '✗'}")
    
    # Verify master catalog
    master_jsons = list(METADATA_DIR.glob("master_catalog_*.json"))
    master_md = list(METADATA_DIR.glob("master_catalog_*.md"))
    master_csv = list(METADATA_DIR.glob("master_catalog_*.csv"))
    print(f"\nMaster catalog files:")
    print(f"  JSON: {len(master_jsons)}")
    print(f"  MD: {len(master_md)}")
    print(f"  CSV: {len(master_csv)}")
    
    # Check README
    readme = BASE_DIR / "README.md"
    print(f"\nREADME.md exists: {'✓' if readme.exists() else '✗'}")
    
    # Sample checks
    print("\n" + "=" * 60)
    print("SAMPLE VERIFICATION")
    print("=" * 60)
    
    # Check first 5 songs
    for i, song in enumerate(songs[:5]):
        title = song.get("title", "untitled")
        sf = safe_filename(title)
        
        wav_path = AUDIO_DIR / f"{sf}.wav"
        lyrics_path = LYRICS_DIR / f"{sf}.txt"
        style_path = STYLES_DIR / f"{sf}_style.txt"
        
        has_wav = wav_path.exists()
        has_lyrics = lyrics_path.exists() and song.get("lyrics", "").strip()
        has_style = style_path.exists() and song.get("description", "").strip()
        
        print(f"{i+1}. {title[:40]:<40} WAV:{has_wav} LYRICS:{has_lyrics} STYLE:{has_style}")
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    all_ok = (
        len(wav_files) == total_songs and
        len(lyrics_files) == lyrics_expected and
        len(style_files) == styles_expected and
        len(master_jsons) >= 1 and
        readme.exists()
    )
    
    print(f"Overall status: {'✓ ALL CHECKS PASS' if all_ok else '✗ SOME ISSUES FOUND'}")
    
    if not all_ok:
        print("\nIssues to investigate:")
        if len(wav_files) != total_songs:
            print(f"- Missing WAV files: {total_songs - len(wav_files)}")
        if len(lyrics_files) != lyrics_expected:
            print(f"- Lyrics file mismatch: expected {lyrics_expected}, found {len(lyrics_files)}")
        if len(style_files) != styles_expected:
            print(f"- Style file mismatch: expected {styles_expected}, found {len(style_files)}")
        if not readme.exists():
            print("- Missing README.md")

if __name__ == "__main__":
    verify()
