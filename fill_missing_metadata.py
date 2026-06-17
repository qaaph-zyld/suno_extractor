#!/usr/bin/env python3
"""
Fill missing lyrics and descriptions for existing liked songs.
Uses Chrome remote debugging + copy button to extract lyrics from clipboard.
Also extracts gpt_description_prompt from embedded page JSON.
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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

DEBUG_PORT = 9222
PAGE_LOAD_WAIT = 2.0
LYRICS_EXPAND_WAIT = 1.0
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

def extract_description_from_json(driver):
    """Extract gpt_description_prompt from embedded JSON script tags."""
    try:
        scripts = driver.find_elements(By.TAG_NAME, "script")
        for s in scripts:
            text = s.get_attribute("textContent") or ""
            if len(text) > 1000 and "gpt_description_prompt" in text:
                # Find JSON object containing gpt_description_prompt
                for match in re.finditer(r'\{[^{}]*"gpt_description_prompt"[^{}]*\}', text):
                    try:
                        data = json.loads(match.group(0))
                        desc = data.get("gpt_description_prompt", "")
                        if desc and len(desc) > 10:
                            return desc
                    except:
                        pass
                # Also try a broader search
                match = re.search(r'"gpt_description_prompt"\s*:\s*"([^"]{20,5000})"', text)
                if match:
                    desc = match.group(1).replace('\\n', '\n').replace('\\"', '"')
                    if len(desc) > 10:
                        return desc
    except Exception as e:
        print("  desc JSON error: %s" % e)
    return ""

def extract_lyrics_via_textarea(driver, url):
    """
    Navigate to song page, click 'Edit Displayed Lyrics',
    then read lyrics from the textarea that appears.
    """
    try:
        driver.get(url)
        time.sleep(PAGE_LOAD_WAIT)

        # Check if page loaded or 404
        if "404" in driver.title or "not found" in driver.page_source.lower():
            print("  Page 404")
            return ""

        # Step 1: Click "Edit Displayed Lyrics" button
        try:
            edit_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Edit Displayed Lyrics')]"))
            )
            edit_btn.click()
            time.sleep(LYRICS_EXPAND_WAIT)
        except Exception as e:
            return ""

        # Step 2: Find textarea with lyrics (may be hidden but value is present)
        lyrics = ""
        try:
            # Primary: look for textarea with substantial content
            # Note: textarea may have displayed=False but value is still accessible
            for textarea in driver.find_elements(By.TAG_NAME, "textarea"):
                val = textarea.get_attribute("value") or ""
                if len(val) > 50:
                    lyrics = val
                    print("  Found lyrics in textarea, len=%d" % len(lyrics))
                    break
        except Exception as e:
            print("  textarea search error: %s" % e)

        # Fallback: contenteditable
        if not lyrics:
            try:
                for el in driver.find_elements(By.XPATH, "//*[@contenteditable='true']"):
                    text = el.text
                    if len(text) > 50:
                        lyrics = text
                        print("  Found lyrics in contenteditable, len=%d" % len(lyrics))
                        break
            except Exception as e:
                print("  contenteditable search error: %s" % e)

        return lyrics

    except Exception as e:
        print("  ERROR: %s" % e)
        return ""

def extract_details(driver, url):
    """Extract both lyrics (via textarea) and description (via JSON)."""
    lyrics = extract_lyrics_via_textarea(driver, url)
    description = extract_description_from_json(driver)
    return lyrics, description

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

    done = load_progress()
    todo = [r for r in missing if r[0] not in done]
    print("Already done: %d" % len(done))
    print("Remaining: %d" % len(todo))
    if not todo:
        print("Nothing to do!")
        return

    driver = connect_to_chrome()
    print("Connected to Chrome")
    done_count = 0

    try:
        for i, (song_id, title, url, old_lyrics, old_desc) in enumerate(todo, 1):
            needs_lyrics = not old_lyrics or len(old_lyrics) == 0
            needs_desc = not old_desc or len(old_desc) == 0
            print("[%d/%d] %s (lyrics:%s desc:%s)" % (i, len(todo), title[:50], "Y" if needs_lyrics else "N", "Y" if needs_desc else "N"))

            new_lyrics, new_desc = extract_details(driver, url)

            final_lyrics = new_lyrics if needs_lyrics and new_lyrics else old_lyrics
            final_desc = new_desc if needs_desc and new_desc else old_desc

            update_db(song_id, final_lyrics, final_desc)

            if (needs_lyrics and new_lyrics) or (needs_desc and new_desc):
                done_count += 1

            done.add(song_id)
            if i % 10 == 0:
                save_progress(done)

            if i % 50 == 0:
                print("  Progress: %d/%d processed, %d improved" % (i, len(todo), done_count))
    finally:
        driver.quit()

    print("Done! %d songs improved out of %d" % (done_count, len(todo)))

if __name__ == "__main__":
    main()
