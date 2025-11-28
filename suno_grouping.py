#!/usr/bin/env python3
"""Grouping utilities for Suno Extractor Pro.

Given a collection JSON (from Selenium extractor or API dump), this script
produces Markdown reports grouping songs:

- by normalized title (all variants of the same named track)
- by lyrics text (songs that share identical lyrics)

Usage (from project root):

    python suno_grouping.py --json-file path/to/collection.json --output suno_groups

If --json-file is omitted, the most recent `suno_liked_songs*.json` from
`suno_songs/` will be used.
"""

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List


@dataclass
class Song:
    raw: Dict

    @property
    def title(self) -> str:
        return str(self.raw.get("title", "")).strip()

    @property
    def artist(self) -> str:
        return str(self.raw.get("artist", "")).strip()

    @property
    def duration(self) -> str:
        return str(self.raw.get("duration", "")).strip()

    @property
    def url(self) -> str:
        return str(self.raw.get("url", "")).strip()

    @property
    def lyrics(self) -> str:
        return str(self.raw.get("lyrics", "")).strip()


def _load_songs(json_file: Path) -> List[Song]:
    with json_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [Song(s) for s in data.get("songs", [])]


def _normalize_title(title: str) -> str:
    t = title.strip().lower()
    return " ".join(t.split())


def _normalize_lyrics(lyrics: str) -> str:
    # Strip whitespace and collapse spaces/newlines so identical texts match
    text = " ".join(lyrics.split())
    return text


def group_by_title(songs: List[Song]) -> Dict[str, List[Song]]:
    groups: Dict[str, List[Song]] = defaultdict(list)
    for s in songs:
        key = _normalize_title(s.title or "")
        if not key:
            key = "(untitled)"
        groups[key].append(s)
    return groups


def group_by_lyrics(songs: List[Song]) -> Dict[str, List[Song]]:
    groups: Dict[str, List[Song]] = defaultdict(list)
    for s in songs:
        if not s.lyrics:
            continue
        key = _normalize_lyrics(s.lyrics)
        if not key:
            continue
        groups[key].append(s)
    return groups


def write_title_report(groups: Dict[str, List[Song]], out_path: Path) -> None:
    total = sum(len(v) for v in groups.values())
    with out_path.open("w", encoding="utf-8") as f:
        f.write("# Suno Library – Grouped by Title\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"Total songs: {total}\n")
        f.write(f"Unique titles: {len(groups)}\n\n")

        # Order by group size (desc), then title
        items = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))

        for title_key, songs in items:
            f.write(f"## {title_key}  (x{len(songs)})\n\n")
            for s in songs:
                line = f"- {s.title or '(untitled)'}"
                if s.artist:
                    line += f" — {s.artist}"
                if s.duration:
                    line += f"  · {s.duration}"
                if s.url:
                    line += f"  · [{s.url}]({s.url})"
                f.write(line + "\n")
            f.write("\n")


def write_lyrics_report(groups: Dict[str, List[Song]], out_path: Path) -> None:
    total_groups = len(groups)
    total_songs = sum(len(v) for v in groups.values())

    with out_path.open("w", encoding="utf-8") as f:
        f.write("# Suno Library – Grouped by Lyrics\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"Total lyric-bearing songs: {total_songs}\n")
        f.write(f"Unique lyric texts: {total_groups}\n\n")

        # Sort by group size desc; show bigger groups first
        items = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))

        for text, songs in items:
            snippet = text.split("\n", 1)[0]
            if len(snippet) > 120:
                snippet = snippet[:117] + "..."
            f.write(f"## Lyrics group (x{len(songs)})\n\n")
            f.write(f"**Snippet:** {snippet!r}\n\n")
            for s in songs:
                line = f"- {s.title or '(untitled)'}"
                if s.artist:
                    line += f" — {s.artist}"
                if s.duration:
                    line += f"  · {s.duration}"
                if s.url:
                    line += f"  · [{s.url}]({s.url})"
                f.write(line + "\n")
            f.write("\n---\n\n")


def auto_find_latest_json() -> Path:
    base = Path("suno_songs")
    candidates = list(base.glob("suno_liked_songs*.json"))
    if not candidates:
        raise SystemExit("No JSON files found in suno_songs/. Run an extraction or API dump first.")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main() -> None:
    parser = argparse.ArgumentParser(description="Group Suno songs by title and lyrics")
    parser.add_argument("--json-file", help="Input collection JSON (defaults to latest in suno_songs)")
    parser.add_argument("--output", default="suno_groups", help="Output directory for Markdown reports")

    args = parser.parse_args()

    if args.json_file:
        json_path = Path(args.json_file)
    else:
        json_path = auto_find_latest_json()

    if not json_path.is_file():
        raise SystemExit(f"JSON file not found: {json_path}")

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    songs = _load_songs(json_path)
    print(f"Loaded {len(songs)} songs from {json_path}")

    title_groups = group_by_title(songs)
    lyrics_groups = group_by_lyrics(songs)

    title_md = out_dir / "group_by_title.md"
    lyrics_md = out_dir / "group_by_lyrics.md"

    write_title_report(title_groups, title_md)
    if lyrics_groups:
        write_lyrics_report(lyrics_groups, lyrics_md)
    else:
        # Still create an empty stub so the file exists
        with lyrics_md.open("w", encoding="utf-8") as f:
            f.write("# Suno Library – Grouped by Lyrics\n\n")
            f.write("No lyrics were present in this collection.\n")

    print("Title groups written to:", title_md)
    print("Lyrics groups written to:", lyrics_md)


if __name__ == "__main__":
    main()
