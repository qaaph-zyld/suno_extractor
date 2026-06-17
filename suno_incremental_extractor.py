#!/usr/bin/env python3
"""
Suno Incremental Extractor — handles virtual scrolling.

Suno's likes page uses virtual scrolling: only ~50 items exist in the DOM
at any time. This script captures song data DURING scrolling, not after,
ensuring every song is recorded even as the DOM recycles elements.

Phase 1: Scroll + capture all song URLs/titles incrementally
Phase 2: Visit each song page for detailed metadata (lyrics, description, tags)
Phase 3: Save to JSON/CSV/MD

Usage:
    python suno_incremental_extractor.py
"""

import io
import sys
import json
import re
import time
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Optional, Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# Fix Windows console encoding for Unicode
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configure logging with UTF-8 encoding
logger = logging.getLogger("suno_incremental")
logger.setLevel(logging.INFO)

# File handler (UTF-8)
fh = logging.FileHandler("suno_incremental_extractor.log", encoding="utf-8")
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(fh)

# Console handler (UTF-8 safe)
ch = logging.StreamHandler(stream=io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace'))
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(ch)

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════
DEBUG_PORT = 9222
OUTPUT_DIR = "suno_songs"
SCROLL_PAUSE = 1.5          # seconds between scrolls
MAX_SCROLLS = 3000          # safety limit
NO_NEW_THRESHOLD = 15       # stop after N scrolls with no new songs
DETAIL_DELAY = 1.5          # seconds between detail page loads
SAVE_CHECKPOINT_EVERY = 100 # save progress every N songs during detail extraction
# ═══════════════════════════════════════════════════════════════


def connect_to_chrome(debug_port: int = 9222) -> webdriver.Chrome:
    """Connect to existing Chrome session."""
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
    driver = webdriver.Chrome(options=options)
    logger.info(f"Connected to Chrome. Current URL: {driver.current_url}")
    return driver


def navigate_to_likes(driver: webdriver.Chrome) -> bool:
    """Navigate to the Suno likes page."""
    current = driver.current_url or ""
    
    # If already on /playlist/liked, stay there
    if "suno.com/playlist/liked" in current:
        logger.info("Already on /playlist/liked page")
        return True
    else:
        driver.get("https://suno.com/playlist/liked")
        time.sleep(5)
    
    # Try to find "Likes" / "Liked" tab/button
    tab_xpaths = [
        "//button[contains(normalize-space(.), 'Likes')]",
        "//a[contains(normalize-space(.), 'Likes')]",
        "//*[@role='tab'][contains(normalize-space(.), 'Likes')]",
        "//button[contains(normalize-space(.), 'Liked')]",
        "//a[contains(normalize-space(.), 'Liked')]",
    ]
    
    for xp in tab_xpaths:
        try:
            el = driver.find_element(By.XPATH, xp)
            if el.is_displayed():
                # Check if already active/selected (aria-pressed, aria-selected, Tailwind active bg class)
                cls = (el.get_attribute("class") or "").lower()
                is_active = (
                    el.get_attribute("aria-pressed") == "true" or
                    el.get_attribute("aria-selected") == "true" or
                    "active" in cls or
                    "selected" in cls or
                    "bg-foreground-primary" in cls
                )
                if is_active:
                    logger.info(f"Likes tab already active, skipping click")
                    return True
                el.click()
                time.sleep(2)
                logger.info(f"Clicked Likes tab via: {xp}")
                return True
        except Exception:
            continue
    
    logger.warning("Could not find Likes tab button, proceeding with current page")
    return False


def capture_songs_from_dom(driver: webdriver.Chrome, known_ids: Set[str]) -> List[Dict]:
    """
    Capture all song data currently visible in the DOM.
    Returns only NEW songs not in known_ids.
    """
    new_songs = []
    
    try:
        # Use JavaScript to extract song data directly — faster than BeautifulSoup
        js_extract = """
        const links = document.querySelectorAll('a[href*="/song/"]');
        const songs = [];
        const seen = new Set();
        
        for (const link of links) {
            const href = link.getAttribute('href') || '';
            const match = href.match(/\\/song\\/([a-f0-9-]+)/);
            if (!match) continue;
            
            const songId = match[1];
            if (seen.has(songId)) continue;
            seen.add(songId);
            
            // Try to get title - check aria-label, title attribute, or text content
            let title = link.getAttribute('aria-label') || link.getAttribute('title') || '';
            if (!title) {
                // Look for any text in the link or its descendants
                title = link.textContent.trim();
            }
            if (!title) {
                // Check parent element for text
                const parent = link.parentElement;
                if (parent) title = parent.textContent.trim().substring(0, 100);
            }
            
            songs.push({
                id: songId,
                url: 'https://suno.com' + href,
                title: title || '(untitled)',
                artist: '',
                duration: '',
                image_url: ''
            });
        }
        
        return songs;
        """
        
        dom_songs = driver.execute_script(js_extract)
        
        for song in (dom_songs or []):
            sid = song.get("id", "")
            if sid and sid not in known_ids:
                new_songs.append(song)
                
    except Exception as e:
        logger.error(f"Error capturing songs from DOM: {e}")
    
    return new_songs


def scroll_and_capture(driver: webdriver.Chrome) -> List[Dict]:
    """
    Phase 1: Scroll through the likes page incrementally,
    capturing song data as it appears in the virtual DOM.
    """
    all_songs: List[Dict] = []
    known_ids: Set[str] = set()
    
    # Initial capture before scrolling
    initial = capture_songs_from_dom(driver, known_ids)
    for s in initial:
        known_ids.add(s["id"])
        all_songs.append(s)
    logger.info(f"Initial capture: {len(initial)} songs")
    
    # JavaScript for scrolling — handles both window and scrollable containers
    scroll_js = """
    // Find scrollable containers
    const containers = Array.from(document.querySelectorAll('*')).filter(el => {
        const cs = getComputedStyle(el);
        return (cs.overflowY === 'auto' || cs.overflowY === 'scroll') && el.scrollHeight > el.clientHeight;
    });
    
    // Scroll main window
    window.scrollBy(0, 800);
    
    // Scroll largest container
    if (containers.length) {
        containers.sort((a,b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
        containers[0].scrollBy(0, 800);
    }
    
    return document.body.scrollHeight;
    """
    
    no_new_count = 0
    scroll_count = 0
    last_total = len(all_songs)
    
    while scroll_count < MAX_SCROLLS:
        # Scroll
        driver.execute_script(scroll_js)
        time.sleep(SCROLL_PAUSE)
        
        # Capture new songs
        new_songs = capture_songs_from_dom(driver, known_ids)
        for s in new_songs:
            known_ids.add(s["id"])
            all_songs.append(s)
        
        scroll_count += 1
        
        if new_songs:
            no_new_count = 0
        else:
            no_new_count += 1
        
        # Log progress
        if scroll_count % 10 == 0:
            logger.info(
                f"Scroll {scroll_count}: +{len(all_songs) - last_total} new this batch, "
                f"{len(all_songs)} total unique songs"
            )
            last_total = len(all_songs)
        
        # Stop condition
        if no_new_count >= NO_NEW_THRESHOLD:
            logger.info(
                f"No new songs for {NO_NEW_THRESHOLD} consecutive scrolls. "
                f"Total: {len(all_songs)} unique songs. Stopping."
            )
            break
    
    # Also try clicking "Show more" / "Load more" buttons
    for text in ["Show more", "Load more", "See more"]:
        try:
            btns = driver.find_elements(By.XPATH, f"//button[contains(., '{text}')]")
            for btn in btns:
                if btn.is_displayed() and btn.is_enabled():
                    btn.click()
                    time.sleep(2)
                    extra = capture_songs_from_dom(driver, known_ids)
                    for s in extra:
                        known_ids.add(s["id"])
                        all_songs.append(s)
                    if extra:
                        logger.info(f"Clicked '{text}' button, found {len(extra)} more songs")
        except Exception:
            pass
    
    logger.info(f"Phase 1 complete: {len(all_songs)} unique songs captured during scrolling")
    return all_songs


def extract_song_details(driver: webdriver.Chrome, song: Dict) -> Dict:
    """
    Phase 2: Visit a song's page and extract full details.
    """
    url = song.get("url", "")
    if not url:
        return song
    
    try:
        driver.get(url)
        time.sleep(DETAIL_DELAY)
        
        # Try to click lyrics tab if present
        try:
            lyrics_btns = driver.find_elements(By.XPATH, 
                "//button[contains(normalize-space(.), 'Lyrics')]")
            for btn in lyrics_btns:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(0.5)
                    break
        except Exception:
            pass
        
        soup = BeautifulSoup(driver.page_source, "lxml")
        
        # Extract lyrics
        lyrics = ""
        lyrics_selectors = [
            {"name": "pre"},
            {"name": "div", "attrs": {"class": re.compile(r"lyrics", re.I)}},
            {"name": "p", "attrs": {"class": re.compile(r"lyrics|whitespace-pre", re.I)}},
            {"name": "div", "attrs": {"data-testid": re.compile(r"lyrics", re.I)}},
        ]
        for sel in lyrics_selectors:
            found = soup.find_all(sel["name"], sel.get("attrs", {}))
            for el in found:
                text = el.get_text("\n", strip=True)
                if len(text) > len(lyrics):
                    lyrics = text
        
        # Also check for whitespace-pre-wrap styled elements (common for lyrics)
        if not lyrics:
            for el in soup.find_all(style=re.compile(r"white-space.*pre")):
                text = el.get_text("\n", strip=True)
                if len(text) > 50 and len(text) > len(lyrics):
                    lyrics = text
        
        song["lyrics"] = lyrics
        
        # Extract description/prompt (style description)
        description = ""
        desc_selectors = [
            {"name": "div", "attrs": {"class": re.compile(r"description|prompt|style", re.I)}},
            {"name": "p", "attrs": {"class": re.compile(r"description|prompt|style|text-muted|text-secondary", re.I)}},
            {"name": "span", "attrs": {"class": re.compile(r"description|prompt|style", re.I)}},
        ]
        for sel in desc_selectors:
            found = soup.find_all(sel["name"], sel.get("attrs", {}))
            for el in found:
                text = el.get_text(strip=True)
                if text and len(text) > len(description) and text != song.get("title", ""):
                    description = text
        
        # Look for meta description as fallback
        if not description:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                description = meta_desc.get("content", "")
        
        song["description"] = description
        
        # Extract tags
        tags = []
        tag_elements = soup.find_all(class_=re.compile(r"tag|badge|chip|genre|style", re.I))
        for el in tag_elements:
            text = el.get_text(strip=True)
            if text and len(text) < 50:
                tags.append(text)
        song["tags"] = list(set(tags))
        
        # Extract additional metadata
        # Artist
        artist_selectors = [
            {"name": "a", "attrs": {"href": re.compile(r"/@")}},
            {"name": "span", "attrs": {"class": re.compile(r"artist|author|creator", re.I)}},
        ]
        for sel in artist_selectors:
            found = soup.find(sel["name"], sel.get("attrs", {}))
            if found:
                text = found.get_text(strip=True)
                if text:
                    song["artist"] = text
                    break
        
        # Created date
        time_el = soup.find("time")
        if time_el:
            song["created_at"] = time_el.get("datetime", time_el.get_text(strip=True))
        
        # Plays/likes counts
        for el in soup.find_all(class_=re.compile(r"play|listen", re.I)):
            text = el.get_text(strip=True)
            if re.match(r"[\d,.]+[KkMm]?$", text):
                song["plays"] = text
                break
        
        for el in soup.find_all(class_=re.compile(r"like|heart|favorite", re.I)):
            text = el.get_text(strip=True)
            if re.match(r"[\d,.]+[KkMm]?$", text):
                song["likes_count"] = text
                break
        
        # Image URL (cover art)
        if not song.get("image_url"):
            img = soup.find("img", src=re.compile(r"cdn.*suno|image_large|cover"))
            if img:
                song["image_url"] = img.get("src", "")
        
        has_lyrics = "with lyrics" if lyrics else "no lyrics"
        has_desc = "with style" if description else "no style"
        logger.info(f"[OK] {song.get('title', '?')} ({has_lyrics}, {has_desc})")
        
    except Exception as e:
        logger.error(f"[FAIL] Detail extraction for {song.get('title', '?')}: {e}")
    
    return song


def save_checkpoint(songs: List[Dict], output_dir: Path, label: str = "checkpoint"):
    """Save intermediate results."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"suno_liked_{label}_{timestamp}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"songs": songs, "total": len(songs), "saved_at": datetime.now().isoformat()}, f, indent=2, ensure_ascii=False)
    logger.info(f"Checkpoint saved: {path} ({len(songs)} songs)")
    return path


def save_final_outputs(songs: List[Dict], output_dir: Path) -> Dict[str, Path]:
    """Save final results in JSON, CSV, and Markdown formats."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outputs = {}
    
    # JSON
    json_path = output_dir / f"suno_liked_songs_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "extracted_at": datetime.now().isoformat(),
                "total_songs": len(songs),
                "extractor": "suno_incremental_extractor"
            },
            "songs": songs
        }, f, indent=2, ensure_ascii=False)
    outputs["json"] = json_path
    logger.info(f"JSON saved: {json_path}")
    
    # CSV
    csv_path = output_dir / f"suno_liked_songs_{timestamp}.csv"
    fieldnames = ["index", "title", "artist", "description", "lyrics", "tags", "duration",
                  "plays", "likes_count", "created_at", "url", "id", "image_url"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for i, song in enumerate(songs, 1):
            row = dict(song)
            row["index"] = i
            row["tags"] = ", ".join(song.get("tags", []))
            writer.writerow(row)
    outputs["csv"] = csv_path
    logger.info(f"CSV saved: {csv_path}")
    
    # Markdown
    md_path = output_dir / f"suno_liked_songs_{timestamp}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Suno Liked Songs Library\n\n")
        f.write(f"**Extracted:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Total Songs:** {len(songs)}\n\n")
        f.write("---\n\n")
        
        for i, song in enumerate(songs, 1):
            f.write(f"## {i}. {song.get('title', '(untitled)')}\n\n")
            f.write("| Field | Value |\n|---|---|\n")
            if song.get("artist"):
                f.write(f"| **Artist** | {song['artist']} |\n")
            if song.get("duration"):
                f.write(f"| **Duration** | {song['duration']} |\n")
            if song.get("plays"):
                f.write(f"| **Plays** | {song['plays']} |\n")
            if song.get("created_at"):
                f.write(f"| **Created** | {song['created_at']} |\n")
            f.write(f"| **URL** | [{song.get('url', '')}]({song.get('url', '')}) |\n\n")
            
            if song.get("tags"):
                f.write(f"**Tags:** {', '.join(song['tags'])}\n\n")
            
            if song.get("description"):
                f.write(f"### Style Description\n\n{song['description']}\n\n")
            
            if song.get("lyrics"):
                f.write(f"### Lyrics\n\n```\n{song['lyrics']}\n```\n\n")
            
            f.write("---\n\n")
    
    outputs["md"] = md_path
    logger.info(f"Markdown saved: {md_path}")
    
    return outputs


def main():
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)
    
    logger.info("=" * 70)
    logger.info("SUNO INCREMENTAL EXTRACTOR - Virtual Scroll Handler")
    logger.info("=" * 70)
    
    # Phase 0: Connect
    driver = connect_to_chrome(DEBUG_PORT)
    
    # Navigate to likes
    navigate_to_likes(driver)
    time.sleep(2)
    
    logger.info(f"Starting extraction from: {driver.current_url}")
    
    # Phase 1: Scroll and capture all song URLs/basic data
    logger.info("=" * 40)
    logger.info("PHASE 1: Scrolling + Incremental Capture")
    logger.info("=" * 40)
    
    songs = scroll_and_capture(driver)
    
    if not songs:
        logger.error("No songs found. Make sure you're on the Suno likes page.")
        return
    
    # Save Phase 1 checkpoint
    save_checkpoint(songs, output_dir, "phase1_urls")
    
    # Load existing song IDs from database to skip detail extraction for known songs
    existing_ids = set()
    db_path = "suno_library.db"
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT id FROM songs")
        existing_ids = {row[0] for row in c.fetchall()}
        conn.close()
        logger.info(f"Loaded {len(existing_ids)} existing song IDs from database")
    except Exception as e:
        logger.warning(f"Could not load existing IDs from DB: {e}")
    
    # Filter to only new songs for Phase 2
    new_songs = [s for s in songs if s.get("id") not in existing_ids]
    existing_songs = [s for s in songs if s.get("id") in existing_ids]
    logger.info(f"Phase 2: {len(new_songs)} new songs to detail, {len(existing_songs)} already in DB (skipped)")
    
    if new_songs:
        logger.info("=" * 40)
        logger.info(f"PHASE 2: Extracting details for {len(new_songs)} new songs")
        logger.info("=" * 40)
        
        for i, song in enumerate(new_songs, 1):
            logger.info(f"[{i}/{len(new_songs)}] {song.get('title', '?')}")
            extract_song_details(driver, song)
            
            # Save checkpoint periodically
            if i % SAVE_CHECKPOINT_EVERY == 0:
                save_checkpoint(songs, output_dir, f"phase2_details_{i}")
    else:
        logger.info("No new songs found — skipping Phase 2 detail extraction")
    
    # Phase 3: Save final outputs
    logger.info("=" * 40)
    logger.info("PHASE 3: Saving final outputs")
    logger.info("=" * 40)
    
    outputs = save_final_outputs(songs, output_dir)
    
    # Summary
    songs_with_lyrics = sum(1 for s in songs if s.get("lyrics"))
    songs_with_desc = sum(1 for s in songs if s.get("description"))
    songs_with_tags = sum(1 for s in songs if s.get("tags"))
    
    logger.info("=" * 70)
    logger.info("EXTRACTION COMPLETE")
    logger.info(f"  Total songs: {len(songs)}")
    logger.info(f"  New songs detailed: {len(new_songs)}")
    logger.info(f"  Existing songs (skipped): {len(existing_songs)}")
    logger.info(f"  With lyrics: {songs_with_lyrics} ({100*songs_with_lyrics/max(len(songs),1):.1f}%)")
    logger.info(f"  With style description: {songs_with_desc} ({100*songs_with_desc/max(len(songs),1):.1f}%)")
    logger.info(f"  With tags: {songs_with_tags} ({100*songs_with_tags/max(len(songs),1):.1f}%)")
    logger.info("=" * 70)
    
    for fmt, path in outputs.items():
        logger.info(f"  {fmt.upper()}: {path}")


if __name__ == "__main__":
    main()
