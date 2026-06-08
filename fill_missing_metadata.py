#!/usr/bin/env python3
"""
Fill missing lyrics and descriptions for existing liked songs.
Connects to Chrome via remote debugging, visits each song page,
and extracts missing metadata directly into the database.
"""
import io, sys, json, sqlite3, re, time, logging
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

DEBUG_PORT = 9222
DETAIL_DELAY = 2.0
PROGRESS_FILE = "metadata_progress.json"

def connect_to_chrome():
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    return webdriver.Chrome(options=options)

def load_progress():
    if Path(PROGRESS_FILE).exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_progress(done_ids):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(done_ids), f, indent=2)

def get_missing_songs():
    conn = sqlite3.connect("suno_library.db")
    c = conn.cursor()
    c.execute('''
        SELECT id, title, url, lyrics, description
        FROM songs
        WHERE is_liked = 1
          AND url IS NOT NULL
          AND (lyrics IS NULL OR length(lyrics) = 0 OR description IS NULL OR length(description) = 0)
    ''')
    rows = c.fetchall()
    conn.close()
    return rows

def extract_details(driver, url):
    try:
        driver.get(url)
        time.sleep(DETAIL_DELAY)
        # Click lyrics tab if present
        try:
            for btn in driver.find_elements(By.XPATH, "//button[contains(normalize-space(.), 'Lyrics')]"):
                if btn.is_displayed():
                    btn.click()
                    time.sleep(0.5)
                    break
        except Exception:
            pass
        soup = BeautifulSoup(driver.page_source, "lxml")
        # Lyrics
        lyrics = ""
        for sel in [
            {"name": "pre"},
            {"name": "div", "attrs": {"class": re.compile(r"lyrics", re.I)}},
            {"name": "p", "attrs": {"class": re.compile(r"lyrics|whitespace-pre", re.I)}},
            {"name": "div", "attrs": {"data-testid": re.compile(r"lyrics", re.I)}},
        ]:
            for el in soup.find_all(sel["name"], sel.get("attrs", {})):
                text = el.get_text("\n", strip=True)
                if len(text) > len(lyrics):
                    lyrics = text
        if not lyrics:
            for el in soup.find_all(style=re.compile(r"white-space.*pre")):
                text = el.get_text("\n", strip=True)
                if len(text) > 50 and len(text) > len(lyrics):
                    lyrics = text
        # Description
        description = ""
        for sel in [
            {"name": "div", "attrs": {"class": re.compile(r"description|prompt|style", re.I)}},
            {"name": "p", "attrs": {"class": re.compile(r"description|prompt|style|text-muted|text-secondary", re.I)}},
            {"name": "span", "attrs": {"class": re.compile(r"description|prompt|style", re.I)}},
        ]:
            for el in soup.find_all(sel["name"], sel.get("attrs", {})):
                text = el.get_text(strip=True)
                if text and len(text) > len(description):
                    description = text
        if not description:
            meta = soup.find("meta", attrs={"name": "description"})
            if meta:
                description = meta.get("content", "")
        return lyrics, description
    except Exception as e:
        print("  ERROR extracting: %s" % e)
        return "", ""

def update_db(song_id, lyrics, description):
    conn = sqlite3.connect("suno_library.db", timeout=30.0)
    c = conn.cursor()
    c.execute('''
        UPDATE songs SET lyrics = ?, description = ?, extracted_at = CURRENT_TIMESTAMP WHERE id = ?
    ''', (lyrics, description, song_id))
    conn.commit()
    conn.close()

def main():
    missing = get_missing_songs()
    print("Total missing metadata: %d" % len(missing))
    if not missing:
        print("Nothing to do!")
        return
    driver = connect_to_chrome()
    print("Connected to Chrome")
    done_count = 0
    try:
        for i, (song_id, title, url, old_lyrics, old_desc) in enumerate(missing, 1):
            needs_lyrics = not old_lyrics or len(old_lyrics) == 0
            needs_desc = not old_desc or len(old_desc) == 0
            print("[%d/%d] %s (lyrics:%s desc:%s)" % (i, len(missing), title[:50], "Y" if needs_lyrics else "N", "Y" if needs_desc else "N"))
            new_lyrics, new_desc = extract_details(driver, url)
            # Only save values if we actually got something
            final_lyrics = new_lyrics if needs_lyrics and new_lyrics else old_lyrics
            final_desc = new_desc if needs_desc and new_desc else old_desc
            update_db(song_id, final_lyrics, final_desc)
            if (needs_lyrics and new_lyrics) or (needs_desc and new_desc):
                done_count += 1
            if i % 50 == 0:
                print("  Progress: %d/%d processed, %d actually improved" % (i, len(missing), done_count))
    finally:
        driver.quit()
    print("Done! %d songs improved out of %d processed" % (done_count, len(missing)))

if __name__ == "__main__":
    main()
