#!/usr/bin/env python3
"""
Audit all downloaded audio files across the workspace to find duplicates
and map files to song IDs.
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict

AUDIO_DIR = Path("suno_library/audio")
DOWNLOADS_DIR = Path("suno_downloads")

def extract_song_id_from_filename(filename):
    """Try to extract a song ID from filename patterns like title_songid.wav"""
    # Pattern: something_8hexchars.wav
    base = Path(filename).stem
    # Look for _ followed by 8 hex chars at the end
    match = re.search(r'_([0-9a-fA-F]{8})$', base)
    if match:
        return match.group(1).lower()
    return None

def audit_directory(directory, label):
    """Audit a directory and return mapping of song_id -> list of files"""
    files = list(directory.glob('*'))
    id_to_files = defaultdict(list)
    no_id_files = []
    
    for f in files:
        if f.is_file():
            song_id = extract_song_id_from_filename(f.name)
            if song_id:
                id_to_files[song_id].append(f.name)
            else:
                no_id_files.append(f.name)
    
    print(f"\n=== {label} ===")
    print(f"Total items: {len(files)}")
    print(f"Files with extractable song ID: {len(id_to_files)}")
    print(f"Files without song ID: {len(no_id_files)}")
    
    # Find duplicates within this directory
    duplicates = {sid: flist for sid, flist in id_to_files.items() if len(flist) > 1}
    print(f"Duplicate song IDs in {label}: {len(duplicates)}")
    
    return id_to_files, no_id_files, duplicates

def main():
    print("Auditing workspace audio files...")
    
    audio_ids, audio_no_id, audio_dups = audit_directory(AUDIO_DIR, "suno_library/audio")
    dl_ids, dl_no_id, dl_dups = audit_directory(DOWNLOADS_DIR, "suno_downloads")
    
    # Cross-directory duplicates
    shared_ids = set(audio_ids.keys()) & set(dl_ids.keys())
    print(f"\n=== Cross-Directory Analysis ===")
    print(f"Song IDs present in BOTH directories: {len(shared_ids)}")
    
    # Unique to each directory
    only_audio = set(audio_ids.keys()) - set(dl_ids.keys())
    only_downloads = set(dl_ids.keys()) - set(audio_ids.keys())
    print(f"Song IDs ONLY in audio/: {len(only_audio)}")
    print(f"Song IDs ONLY in downloads/: {len(only_downloads)}")
    
    # Save audit report
    report = {
        'audio_dir': {
            'total_files': sum(len(v) for v in audio_ids.values()) + len(audio_no_id),
            'files_with_id': len(audio_ids),
            'files_without_id': len(audio_no_id),
            'duplicate_ids': {k: v for k, v in audio_dups.items()},
        },
        'downloads_dir': {
            'total_files': sum(len(v) for v in dl_ids.values()) + len(dl_no_id),
            'files_with_id': len(dl_ids),
            'files_without_id': len(dl_no_id),
            'duplicate_ids': {k: v for k, v in dl_dups.items()},
        },
        'cross_directory': {
            'shared_ids': list(shared_ids)[:100],  # Limit for readability
            'shared_count': len(shared_ids),
            'only_audio_count': len(only_audio),
            'only_downloads_count': len(only_downloads),
        }
    }
    
    with open('workspace_audit_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\nAudit report saved to workspace_audit_report.json")

if __name__ == "__main__":
    main()
