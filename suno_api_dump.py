#!/usr/bin/env python3
"""Dump ALL liked songs via Suno API using existing browser session.

This script:
- Attaches to your existing Chrome with Suno logged in (remote debugging port)
- Extracts cookies from the browser
- Uses `SunoAPI` to call the unofficial API and fetch all liked songs (paginated)
- Saves them in the same JSON structure as the Selenium extractor

Usage (from project root):

    python suno_api_dump.py --browser chrome --port 9222 --output suno_songs

Make sure Chrome is started with `--remote-debugging-port=9222` and you are
logged in to https://suno.com/me?liked=true.
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from suno_extractor import SunoExtractor
from suno_api import SunoAPI


logger = logging.getLogger(__name__)


def dump_liked(browser: str = "chrome", port: int = 9222, output_dir: str = "suno_songs") -> Path:
    """Dump all liked songs to a JSON file and return its path."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Attaching to existing %s (port %s)", browser, port)
    extractor = SunoExtractor(output_dir=str(out_dir), browser=browser)
    extractor.connect_to_existing_browser(debug_port=port)

    # Ensure we're on suno.com domain to get cookies
    current_url = extractor.driver.current_url
    if "suno.com" not in current_url:
        logger.info("Navigating to suno.com to extract cookies...")
        extractor.driver.get("https://suno.com/me?liked=true")
        import time
        time.sleep(3)

    api = SunoAPI()
    cookie = api.extract_cookie_from_browser(extractor.driver)
    logger.info("Extracted cookie string (%d chars)", len(cookie))
    
    # Log some cookie names for debugging
    cookies = extractor.driver.get_cookies()
    cookie_names = [c['name'] for c in cookies]
    logger.info("Cookie names: %s", cookie_names[:10] if len(cookie_names) > 10 else cookie_names)

    logger.info("Fetching ALL liked songs via API...")
    songs = api.get_all_liked_songs(max_pages=200)
    logger.info("API returned %d liked songs", len(songs))

    wrapped = []
    for idx, s in enumerate(songs, 1):
        wrapped.append(
            {
                "index": idx,
                "title": s.get("title", "") or f"Song {idx}",
                "artist": s.get("artist", ""),
                "description": s.get("description", ""),
                "lyrics": s.get("lyrics", ""),
                "tags": s.get("tags", []),
                "duration": s.get("duration", ""),
                "plays": str(s.get("plays", "")),
                "likes": str(s.get("likes", "")),
                "created_at": s.get("created_at", ""),
                "url": s.get("url", ""),
                "image_url": s.get("image_url", ""),
                "liked": True,
                "disliked": False,
                "source_tab": "likes",
            }
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"suno_liked_songs_api_{timestamp}.json"

    payload = {
        "metadata": {
            "extracted_at": datetime.now().isoformat(),
            "total_songs": len(wrapped),
            "source": "api_liked",
            "extractor_version": "2.0",
        },
        "songs": wrapped,
    }

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    logger.info("Saved API liked dump to %s", out_path)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump all liked songs via Suno API")
    parser.add_argument("--browser", default="chrome", choices=["chrome", "firefox"])
    parser.add_argument("--port", type=int, default=9222, help="Remote debugging port")
    parser.add_argument("--output", default="suno_songs", help="Output directory")

    args = parser.parse_args()

    path = dump_liked(browser=args.browser, port=args.port, output_dir=args.output)
    print(f"API liked dump written to: {path}")


if __name__ == "__main__":
    main()
