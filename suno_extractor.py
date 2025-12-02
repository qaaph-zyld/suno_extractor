#!/usr/bin/env python3
"""
Suno Liked Songs Extractor - Existing Browser Session
Connects to already-open browser with Suno logged in
"""

import json
import time
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set
import re
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

# Shared utilities
from suno_utils import ExtractionError

# Optional: auto-manage drivers
try:
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    _WDM_AVAILABLE = True
except Exception:
    _WDM_AVAILABLE = False

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('suno_extractor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SunoExtractor:
    """Extract liked songs from existing Suno browser session"""
    
    def __init__(self, output_dir: str = "suno_songs", browser: str = "chrome"):
        """
        Initialize extractor for existing browser session
        
        Args:
            output_dir: Directory to save extracted songs
            browser: 'chrome' or 'firefox'
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.browser_type = browser.lower()
        self.driver = None
        self.wait = None
        self.extracted_urls: Set[str] = set()
        
    def connect_to_existing_browser(self, debug_port: int = None):
        """
        Connect to existing browser session
        
        Args:
            debug_port: Remote debugging port (9222 for Chrome, 9223 for Firefox)
        """
        if self.browser_type == "chrome":
            debug_port = debug_port or 9222
            logger.info(f"Connecting to Chrome on port {debug_port}...")
            
            options = ChromeOptions()
            options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
            
            try:
                if _WDM_AVAILABLE:
                    service = ChromeService(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=options)
                else:
                    self.driver = webdriver.Chrome(options=options)
                self.wait = WebDriverWait(self.driver, 20)
                logger.info("✓ Connected to Chrome successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Chrome: {e}")
                logger.info(f"Start Chrome with: google-chrome --remote-debugging-port={debug_port}")
                raise ExtractionError(
                    f"Cannot connect to Chrome on port {debug_port}. "
                    f"Start Chrome with: chrome --remote-debugging-port={debug_port}"
                ) from e
                
        elif self.browser_type == "firefox":
            # Selenium cannot reliably attach to an already-running Firefox
            # session via marionette. Recommend using Chrome with debuggerAddress.
            logger.error("Attaching to an existing Firefox session is not supported reliably. "
                         "Please use Chrome with --remote-debugging-port.")
            raise ExtractionError(
                "Firefox attach unsupported. Launch Chrome with --remote-debugging-port and set browser='chrome'."
            )
        else:
            raise ExtractionError(f"Unsupported browser: {self.browser_type}")
    
    def navigate_to_liked_songs(self):
        """Navigate to liked songs page in existing session"""
        logger.info("Navigating to liked songs...")
        
        current_url = self.driver.current_url
        logger.info(f"Current URL: {current_url}")
        
        # Navigate to library
        if "suno.com" not in current_url:
            logger.info("Navigating to Suno...")
            self.driver.get("https://suno.com/me")
            time.sleep(3)
        elif "library" not in current_url:
            self.driver.get("https://suno.com/me")
            time.sleep(3)
        
        # Find and click Liked/Favorites tab
        try:
            liked_selectors = [
                "//button[contains(., 'Liked')]",
                "//button[contains(., 'Favorites')]",
                "//a[contains(., 'Liked')]",
                "//div[contains(@class, 'tab')][contains(., 'Liked')]",
                "//*[@role='tab'][contains(., 'Liked')]"
            ]
            
            for selector in liked_selectors:
                try:
                    liked_tab = self.driver.find_element(By.XPATH, selector)
                    liked_tab.click()
                    logger.info("✓ Clicked Liked tab")
                    time.sleep(2)
                    return
                except NoSuchElementException:
                    continue
            
            logger.warning("Could not find Liked tab - assuming already on correct page")
            
        except Exception as e:
            logger.warning(f"Navigation issue: {e}")
    
    def scroll_to_load_all(self, max_scrolls: int = 600, scroll_pause: float = 1.2):
        """
        Scroll page to trigger lazy loading of all songs
        
        Args:
            max_scrolls: Maximum scroll iterations
            scroll_pause: Seconds to wait between scrolls
        """
        logger.info("Loading all songs via scrolling...")

        # Helper: scroll window and the largest scrollable container
        scroll_js = """
        const containers = Array.from(document.querySelectorAll('*')).filter(el => {
          const cs = getComputedStyle(el);
          return (cs.overflowY === 'auto' || cs.overflowY === 'scroll') && el.scrollHeight > el.clientHeight;
        });
        let maxHeight = document.body.scrollHeight;
        // Scroll the main window
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
        // Scroll the largest container if any
        if (containers.length) {
          containers.sort((a,b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
          const el = containers[0];
          el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
          maxHeight = Math.max(maxHeight, el.scrollHeight);
        }
        return maxHeight;
        """

        def click_show_more_buttons():
            try:
                buttons = self.driver.find_elements(By.XPATH, "//button[normalize-space()[matches(., 'Show more|Load more|See more', 'i')]]")
            except Exception:
                # Fallback: simple contains matching
                buttons = []
                for text in ["Show more", "Load more", "See more", "More"]:
                    try:
                        buttons.extend(self.driver.find_elements(By.XPATH, f"//button[contains(., '{text}')]"))
                    except Exception:
                        pass
            clicked = 0
            for b in buttons:
                try:
                    if b.is_displayed() and b.is_enabled():
                        b.click()
                        clicked += 1
                        time.sleep(0.5)
                except Exception:
                    continue
            if clicked:
                logger.debug(f"Clicked {clicked} 'show more' buttons")

        last_height = self.driver.execute_script("return document.body.scrollHeight")
        no_change_count = 0
        scroll_count = 0
        # Track growth by unique song links found
        try:
            prev_count = len(self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/song/']"))
        except Exception:
            prev_count = 0

        while scroll_count < max_scrolls:
            # Attempt to click any 'show more' buttons that reveal additional content
            click_show_more_buttons()

            # Smooth scroll (window + largest container)
            new_height = self.driver.execute_script(scroll_js)
            time.sleep(scroll_pause)
            try:
                new_count = len(self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/song/']"))
            except Exception:
                new_count = prev_count

            if new_height == last_height and new_count == prev_count:
                no_change_count += 1
                if no_change_count >= 5:
                    logger.info(f"✓ Reached end of page (no new content after {no_change_count} attempts, found {new_count} songs)")
                    break
            else:
                no_change_count = 0

            last_height = new_height
            prev_count = new_count
            scroll_count += 1

            if scroll_count % 10 == 0:
                logger.info(f"Scrolled {scroll_count} times...")

        # Scroll back to top for complete DOM access
        self.driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'});")
        time.sleep(1)

        logger.info(f"✓ Finished scrolling ({scroll_count} iterations)")
    
    def extract_all_songs(self) -> List[Dict]:
        """
        Extract all visible song data from current page
        
        Returns:
            List of song dictionaries
        """
        logger.info("Extracting song data from page...")
        
        # Get full page source
        page_source = self.driver.page_source
        soup = BeautifulSoup(page_source, 'lxml')
        
        songs = []

        # Scope extraction to the primary collection container to avoid picking up feed/recommended links
        candidate_containers = []
        try:
            candidate_containers = soup.find_all(
                lambda t: (
                    t.name in ('div', 'main', 'section') and (
                        (t.get('role') in ('grid', 'list')) or
                        (t.get('class') and any(re.search(r'library|grid|list|collection|items|content|scroll|infinite', c, re.I) for c in (t.get('class') or [])))
                    )
                )
            )
        except Exception:
            candidate_containers = []

        # Always include body as a last-resort candidate
        if soup.body and soup.body not in candidate_containers:
            candidate_containers.append(soup.body)

        def count_song_links(node):
            try:
                return len(node.find_all('a', href=re.compile(r'/song/')))
            except Exception:
                return 0

        best = None
        best_count = -1
        for node in candidate_containers:
            c = count_song_links(node)
            if c > best_count:
                best, best_count = node, c

        container = best or soup

        # Strategy 1: Find song cards/items within the selected container
        song_selectors = [
            {'name': 'song-card', 'attrs': {'class': re.compile(r'song|track|card|item', re.I)}},
            {'name': 'article'},
            {'name': 'div', 'attrs': {'data-testid': re.compile(r'song|track', re.I)}},
            {'name': 'a', 'attrs': {'href': re.compile(r'/song/')}},
        ]

        song_elements = []
        for selector in song_selectors:
            try:
                elements = container.find_all(selector['name'], selector.get('attrs', {}))
            except Exception:
                elements = []
            if elements:
                logger.info(f"Found {len(elements)} elements using {selector} in primary container")
                song_elements = elements
                break

        if not song_elements:
            logger.warning("No song elements found with standard selectors in container; falling back to link list")
            # Fallback: find all links with /song/ in href within the container only
            song_elements = container.find_all('a', href=re.compile(r'/song/'))

        logger.info(f"Processing {len(song_elements)} potential song elements from container...")
        
        # Extract data from each element
        for idx, element in enumerate(song_elements, 1):
            try:
                song_data = self._parse_song_element(element, idx)
                if song_data and song_data['url'] not in self.extracted_urls:
                    songs.append(song_data)
                    self.extracted_urls.add(song_data['url'])
                    logger.debug(f"Extracted: {song_data['title']}")
            except Exception as e:
                logger.debug(f"Error parsing element {idx}: {e}")
                continue
        logger.info(f"OK Extracted {len(songs)} unique songs from primary container")
        return songs

    def navigate_to_tab(self, tab: str):
        """Navigate to a specific tab on /me page (e.g., 'likes', 'creations')."""
        base = "https://suno.com/me"
        tab = (tab or '').lower()
        try_urls = []
        if tab == 'likes' or tab == 'liked':
            # Try explicit liked query param first, then tab-based, then base
            try_urls = [f"{base}?liked=true", f"{base}?tab=likes", base]
            labels = ["Likes", "Liked", "Favorites"]
        elif tab == 'creations' or tab == 'created':
            try_urls = [f"{base}?tab=creations", base]
            labels = ["Creations", "Created", "My songs", "My Creations"]
        else:
            try_urls = [base]
            labels = []

        for url in try_urls:
            self.driver.get(url)
            time.sleep(2)

            if labels:
                # Try to click the desired tab
                xpaths = []
                for lbl in labels:
                    xpaths.extend([
                        f"//button[contains(normalize-space(.), '{lbl}')]",
                        f"//a[contains(normalize-space(.), '{lbl}')]",
                        f"//*[@role='tab'][contains(normalize-space(.), '{lbl}')]",
                        f"//div[contains(@class, 'tab')][contains(normalize-space(.), '{lbl}')]"
                    ])
                for xp in xpaths:
                    try:
                        el = self.driver.find_element(By.XPATH, xp)
                        el.click()
                        time.sleep(1.2)
                        return
                    except Exception:
                        continue
                # If no tab clicked, assume correct page
                return
        # Fallback: go to base and return
        self.driver.get(base)
        time.sleep(1.2)

    def _click_next_page(self) -> bool:
        """Try to click a generic 'next page' control on the library view.

        Returns:
            True if a click was performed and page content likely changed.
        """
        logger.info("Checking for next page button...")

        # Snapshot current state to detect whether page actually changes
        try:
            before_url = self.driver.current_url
            before_links = {
                el.get_attribute("href")
                for el in self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/song/']")
                if el.get_attribute("href")
            }
        except Exception:
            before_url = ""
            before_links = set()

        candidates = []
        xpaths = [
            # Buttons/links with accessible labels
            "//button[contains(@aria-label, 'Next') or contains(@title, 'Next')]",
            "//a[contains(@aria-label, 'Next') or contains(@title, 'Next')]",
            # Common pagination arrows
            "//button[normalize-space(text())='>' or normalize-space(text())='›' or normalize-space(text())='»']",
            "//a[normalize-space(text())='>' or normalize-space(text())='›' or normalize-space(text())='»']",
            # data-testid based selectors
            "//*[@data-testid='pagination-next' or contains(@data-testid, 'next-page')]",
        ]

        for xp in xpaths:
            try:
                els = self.driver.find_elements(By.XPATH, xp)
                if els:
                    candidates.extend(els)
            except Exception:
                continue

        clicked = False
        for el in candidates:
            try:
                if not el.is_displayed() or not el.is_enabled():
                    continue
                # Scroll element into view and click
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                time.sleep(0.3)
                el.click()
                clicked = True
                logger.info("Clicked next page button")
                break
            except Exception:
                continue

        if not clicked:
            logger.info("No next page control found; assuming last page")
            return False

        # Wait for new page content
        time.sleep(3.0)
        try:
            after_url = self.driver.current_url
            after_links = {
                el.get_attribute("href")
                for el in self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/song/']")
                if el.get_attribute("href")
            }
        except Exception:
            after_url = before_url
            after_links = before_links

        # Detect whether we actually navigated to a new page of songs.
        # In the current SPA, URL and count may remain the same across pages,
        # so we compare the set of hrefs instead of just the count.
        if after_url == before_url and after_links == before_links:
            logger.info("Next page click did not change song list; assuming last page")
            return False

        new_links = after_links - before_links
        logger.info(f"Next page appears to have {len(new_links)} new song links")
        return True

    def _extract_all_pages_for_tab(self, tab: str, max_pages: int = 50) -> List[Dict]:
        """Extract songs from all paginated pages for the given tab.

        This will:
        - Scroll within each page to load all rows
        - Extract all visible songs on that page
        - Click the pagination "next" arrow (if present) and repeat
        """
        all_songs: List[Dict] = []
        page_index = 1

        while page_index <= max_pages:
            logger.info(f"Tab '{tab}': extracting page {page_index}...")

            # Ensure current page is fully loaded
            self.scroll_to_load_all()

            before_urls = set(self.extracted_urls)
            chunk = self.extract_all_songs()

            if not chunk:
                logger.info("No songs found on this page; stopping pagination")
                break

            for s in chunk:
                s['source_tab'] = tab
            all_songs.extend(chunk)

            logger.info(
                f"Page {page_index}: {len(chunk)} songs, "
                f"total unique so far: {len(self.extracted_urls)}"
            )

            # Try to go to next page; stop if no navigation or no new songs
            if not self._click_next_page():
                break

            page_index += 1

            # Safety: if no new URLs were added on last page, break to avoid loops
            if before_urls == self.extracted_urls:
                logger.info("No new songs detected after page change; stopping pagination")
                break

        return all_songs
    
    def _parse_song_element(self, element, idx: int) -> Optional[Dict]:
        """
        Parse individual song element with robust selectors
        
        Args:
            element: BeautifulSoup element
            idx: Song index
            
        Returns:
            Song data dictionary or None
        """
        song_data = {
            'index': idx,
            'title': '',
            'artist': '',
            'description': '',
            'lyrics': '',
            'tags': [],
            'duration': '',
            'plays': '',
            'likes': '',
            'created_at': '',
            'url': '',
            'image_url': '',
            'liked': False,
            'disliked': False,
            'source_tab': ''
        }
        
        # Extract URL (required field)
        link = element.find('a', href=re.compile(r'/song/'))
        if not link:
            if element.name == 'a' and element.get('href') and '/song/' in element.get('href'):
                link = element
            else:
                return None
        
        href = link.get('href', '')
        song_data['url'] = f"https://suno.com{href}" if href.startswith('/') else href
        
        # Extract title
        title_selectors = [
            element.find(['h1', 'h2', 'h3', 'h4']),
            element.find(class_=re.compile(r'title|name|heading', re.I)),
            element.find('span', class_=re.compile(r'song.*name', re.I)),
            link
        ]
        
        for title_elem in title_selectors:
            if title_elem and title_elem.get_text(strip=True):
                song_data['title'] = title_elem.get_text(strip=True)
                break
        
        if not song_data['title']:
            song_data['title'] = f"Song {idx}"
        
        # Extract artist/creator
        artist_selectors = [
            element.find(class_=re.compile(r'artist|creator|author', re.I)),
            element.find('span', class_=re.compile(r'by|user', re.I)),
            element.find('a', href=re.compile(r'/@'))
        ]
        
        for artist_elem in artist_selectors:
            if artist_elem:
                song_data['artist'] = artist_elem.get_text(strip=True)
                break
        
        # Extract description/prompt
        desc_elem = element.find(class_=re.compile(r'description|prompt|caption', re.I))
        if desc_elem:
            song_data['description'] = desc_elem.get_text(strip=True)
        
        # Extract tags
        tag_elements = element.find_all(class_=re.compile(r'tag|genre|style', re.I))
        song_data['tags'] = [
            tag.get_text(strip=True) 
            for tag in tag_elements 
            if tag.get_text(strip=True)
        ]

        # Heuristics: liked/disliked state
        try:
            # Liked (heart/favorite)
            like_btn = element.find(lambda t: (
                (t.name in ('button','span','div','a')) and (
                    (t.get('aria-label') and re.search(r'like|favorite|heart', t.get('aria-label'), re.I)) or
                    (t.get('class') and any(re.search(r'like|favorite|heart', c, re.I) for c in (t.get('class') or [])))
                )
            ))
            if like_btn and (like_btn.get('aria-pressed') == 'true' or like_btn.get('data-active') == 'true'):
                song_data['liked'] = True
        except Exception:
            pass

        try:
            # Disliked (thumb-down)
            dislike_btn = element.find(lambda t: (
                (t.name in ('button','span','div','a')) and (
                    (t.get('aria-label') and re.search(r'dislike|thumbs?-down', t.get('aria-label'), re.I)) or
                    (t.get('class') and any(re.search(r'dislike|thumbs?-down', c, re.I) for c in (t.get('class') or [])))
                )
            ))
            if dislike_btn and (dislike_btn.get('aria-pressed') == 'true' or dislike_btn.get('data-active') == 'true'):
                song_data['disliked'] = True
        except Exception:
            pass
        
        # Extract image
        img = element.find('img')
        if img and img.get('src'):
            song_data['image_url'] = img.get('src')
        
        # Extract metadata (duration, plays, etc.)
        meta_elements = element.find_all(['span', 'div', 'time'])
        for meta in meta_elements:
            text = meta.get_text(strip=True)
            
            # Duration pattern (MM:SS)
            if re.match(r'\d{1,2}:\d{2}', text):
                song_data['duration'] = text
            
            # Plays count
            if re.search(r'\d+.*play', text, re.I):
                song_data['plays'] = text
            
            # Likes count
            if re.search(r'\d+.*like', text, re.I):
                song_data['likes'] = text
            
            # Date
            if re.search(r'\d{4}-\d{2}-\d{2}|\d+\s*(day|week|month|year)', text, re.I):
                song_data['created_at'] = text
        
        return song_data
    
    def extract_detailed_info(self, songs: List[Dict], delay: float = 1.5) -> List[Dict]:
        """
        Visit each song page to extract full lyrics and details
        
        Args:
            songs: List of basic song data
            delay: Seconds to wait between page loads
            
        Returns:
            Enhanced song data with full details
        """
        logger.info(f"Extracting detailed information for {len(songs)} songs...")
        
        for idx, song in enumerate(songs, 1):
            try:
                logger.info(f"[{idx}/{len(songs)}] Loading: {song['title']}")
                
                # Navigate to song page
                self.driver.get(song['url'])
                time.sleep(delay)
                
                # Try to reveal lyrics tab or expanded content before parsing
                try:
                    lyrics_click_xpaths = [
                        "//button[contains(., 'Lyrics')]",
                        "//*[@role='tab'][contains(., 'Lyrics')]",
                        "//div[contains(@class, 'tab')][contains(., 'Lyrics')]",
                        "//a[contains(., 'Lyrics')]",
                        "//button[contains(., 'Show more')]"
                    ]
                    for xp in lyrics_click_xpaths:
                        try:
                            el = self.driver.find_element(By.XPATH, xp)
                            if el.is_displayed() and el.is_enabled():
                                el.click()
                                time.sleep(0.6)
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

                # Parse song page
                soup = BeautifulSoup(self.driver.page_source, 'lxml')
                
                # Extract full lyrics - try multiple strategies
                lyrics_text = ""
                
                # Strategy 1: Look for elements with lyrics-related classes
                lyrics_selectors = [
                    soup.find('pre', class_=re.compile(r'lyrics', re.I)),
                    soup.find('div', class_=re.compile(r'^lyrics$', re.I)),  # Exact match
                    soup.find(attrs={'data-lyrics': True}),
                ]
                for lyrics_elem in lyrics_selectors:
                    if lyrics_elem:
                        text = lyrics_elem.get_text(separator='\n', strip=True)
                        # Filter out navigation text
                        if len(text) > 50 and 'Home' not in text[:100] and 'Create' not in text[:100]:
                            if len(text) > len(lyrics_text):
                                lyrics_text = text
                
                # Strategy 2: Find the smallest element containing verse/chorus markers
                # (to avoid grabbing the whole page)
                if not lyrics_text:
                    candidates = []
                    for elem in soup.find_all(['div', 'pre', 'p', 'span']):
                        # Skip navigation/header elements
                        if elem.find_parent(['nav', 'header', 'footer']):
                            continue
                        classes = ' '.join(elem.get('class', []))
                        if re.search(r'nav|menu|header|footer|sidebar', classes, re.I):
                            continue
                        
                        text = elem.get_text(separator='\n', strip=True)
                        # Must have lyrics markers and reasonable length
                        if re.search(r'\[Verse|\[Chorus|\[Bridge|\[Intro|\[Outro', text, re.I):
                            if 50 < len(text) < 5000:  # Reasonable lyrics length
                                # Skip if it contains navigation keywords
                                if 'Home' in text[:100] or 'Create' in text[:100] or 'Library' in text[:100]:
                                    continue
                                candidates.append((len(text), text, elem))
                    
                    # Pick the smallest valid candidate (most specific)
                    if candidates:
                        candidates.sort(key=lambda x: x[0])
                        lyrics_text = candidates[0][1]
                
                # Strategy 3: Look for whitespace-pre elements (common for lyrics)
                if not lyrics_text:
                    for elem in soup.find_all(style=re.compile(r'white-space.*pre', re.I)):
                        if elem.find_parent(['nav', 'header', 'footer']):
                            continue
                        text = elem.get_text(separator='\n', strip=True)
                        if 50 < len(text) < 5000:
                            if 'Home' not in text[:100] and 'Create' not in text[:100]:
                                if len(text) > len(lyrics_text):
                                    lyrics_text = text
                
                if lyrics_text:
                    song['lyrics'] = lyrics_text
                    logger.debug(f"Found lyrics ({len(lyrics_text)} chars) for {song['title']}")
                
                # Extract full description
                desc_selectors = [
                    soup.find('div', class_=re.compile(r'description|prompt', re.I)),
                    soup.find('p', class_=re.compile(r'description', re.I)),
                    soup.find(attrs={'data-description': True})
                ]
                
                for desc_elem in desc_selectors:
                    if desc_elem:
                        desc_text = desc_elem.get_text(strip=True)
                        if len(desc_text) > len(song['description']):
                            song['description'] = desc_text
                            break
                
                # Extract additional metadata
                meta_elements = soup.find_all(['span', 'div', 'p'], 
                                             class_=re.compile(r'meta|info|stat', re.I))
                
                for meta in meta_elements:
                    text = meta.get_text(strip=True).lower()
                    
                    if not song['duration'] and re.search(r'\d:\d{2}', text):
                        song['duration'] = meta.get_text(strip=True)
                    
                    if not song['plays'] and 'play' in text:
                        song['plays'] = meta.get_text(strip=True)
                    
                    if not song['likes'] and 'like' in text:
                        song['likes'] = meta.get_text(strip=True)
                    
                    if not song['created_at'] and ('ago' in text or 'created' in text):
                        song['created_at'] = meta.get_text(strip=True)
                
                # Extract better tags if available
                tag_elements = soup.find_all(class_=re.compile(r'tag|genre|style|badge', re.I))
                if tag_elements:
                    new_tags = [tag.get_text(strip=True) for tag in tag_elements]
                    song['tags'] = list(set(song['tags'] + new_tags))
                
                has_lyrics = "with lyrics" if song.get('lyrics') else "no lyrics"
                logger.info(f"✓ Extracted details for: {song['title']} ({has_lyrics})")
                
            except Exception as e:
                logger.error(f"✗ Failed to extract details for {song.get('title', 'unknown')}: {e}")
                continue
        
        logger.info(f"Detailed extraction complete: {sum(1 for s in songs if s.get('lyrics'))} songs have lyrics")
        return songs
    
    def save_to_markdown(self, songs: List[Dict], filename: str = None) -> Path:
        """
        Save songs to formatted Markdown file
        
        Args:
            songs: List of song data
            filename: Output filename (auto-generated if None)
            
        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"suno_liked_songs_{timestamp}.md"
        
        filepath = self.output_dir / filename
        
        logger.info(f"Saving {len(songs)} songs to {filepath}...")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            # Header
            f.write("# 🎵 Suno Liked Songs\n\n")
            f.write(f"**Extracted:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Total Songs:** {len(songs)}\n\n")
            f.write("---\n\n")
            
            # Table of Contents
            f.write("## 📑 Table of Contents\n\n")
            for song in songs:
                anchor = re.sub(r'[^\w\s-]', '', song['title'].lower())
                anchor = re.sub(r'[-\s]+', '-', anchor)
                f.write(f"{song['index']}. [{song['title']}](#{anchor})\n")
            f.write("\n---\n\n")
            
            # Individual songs
            for song in songs:
                # Song header
                f.write(f"## {song['index']}. {song['title']}\n\n")
                
                # Metadata table
                f.write("| Attribute | Value |\n")
                f.write("|-----------|-------|\n")
                
                if song.get('artist'):
                    f.write(f"| **Artist** | {song['artist']} |\n")
                if song.get('duration'):
                    f.write(f"| **Duration** | {song['duration']} |\n")
                if song.get('plays'):
                    f.write(f"| **Plays** | {song['plays']} |\n")
                if song.get('likes'):
                    f.write(f"| **Likes** | {song['likes']} |\n")
                if song.get('created_at'):
                    f.write(f"| **Created** | {song['created_at']} |\n")
                if song.get('url'):
                    f.write(f"| **URL** | [{song['url']}]({song['url']}) |\n")
                
                f.write("\n")
                
                # Tags
                if song.get('tags'):
                    f.write("**Tags:** ")
                    f.write(" • ".join([f"`{tag}`" for tag in song['tags']]))
                    f.write("\n\n")
                
                # Description
                if song.get('description'):
                    f.write("### 📝 Description\n\n")
                    f.write(f"{song['description']}\n\n")
                
                # Lyrics
                if song.get('lyrics'):
                    f.write("### 🎤 Lyrics\n\n")
                    f.write("```\n")
                    f.write(song['lyrics'])
                    f.write("\n```\n\n")
                
                f.write("---\n\n")
        
        logger.info(f"✓ Markdown saved to: {filepath}")
        return filepath
    
    def save_to_json(self, songs: List[Dict], filename: str = None) -> Path:
        """
        Save songs to JSON format with full metadata
        
        Args:
            songs: List of song data
            filename: Output filename (auto-generated if None)
            
        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"suno_liked_songs_{timestamp}.json"
        
        filepath = self.output_dir / filename
        
        logger.info(f"Saving JSON backup to {filepath}...")
        
        export_data = {
            'metadata': {
                'extracted_at': datetime.now().isoformat(),
                'total_songs': len(songs),
                'extractor_version': '2.0'
            },
            'songs': songs
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ JSON saved to: {filepath}")
        return filepath
    
    def save_to_csv(self, songs: List[Dict], filename: str = None) -> Path:
        """
        Save songs to CSV format for spreadsheet analysis
        
        Args:
            songs: List of song data
            filename: Output filename (auto-generated if None)
            
        Returns:
            Path to saved file
        """
        import csv
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"suno_liked_songs_{timestamp}.csv"
        
        filepath = self.output_dir / filename
        
        logger.info(f"Saving CSV to {filepath}...")
        
        # Define CSV columns
        fieldnames = ['index', 'title', 'artist', 'duration', 'plays', 'likes', 
                     'created_at', 'tags', 'description', 'lyrics', 'url', 'image_url',
                     'liked', 'disliked', 'source_tab']
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            for song in songs:
                # Convert tags list to comma-separated string
                row = song.copy()
                row['tags'] = ', '.join(song.get('tags', []))
                writer.writerow(row)
        
        logger.info(f"✓ CSV saved to: {filepath}")
        return filepath
    
    def run_extraction(self, extract_details: bool = True, 
                      save_formats: List[str] = None,
                      tabs: List[str] = None,
                      exclude_disliked: bool = True) -> Dict[str, Path]:
        """
        Execute complete extraction workflow
        
        Args:
            extract_details: Visit each song for full details
            save_formats: List of formats ['md', 'json', 'csv']
            
        Returns:
            Dictionary mapping format to filepath
        """
        if save_formats is None:
            save_formats = ['md', 'json']
        
        output_files = {}
        
        try:
            # If tabs not specified, restrict to user-owned views to avoid feed/recommendations
            if tabs is None:
                tabs = ['creations']

            songs: List[Dict] = []

            if tabs:
                for tab in tabs:
                    logger.info(f"Navigating to tab: {tab}")
                    # Navigate to the specific tab
                    self.navigate_to_tab(tab)

                    # Extract across all paginated pages for this tab
                    chunk = self._extract_all_pages_for_tab(tab)
                    songs.extend(chunk)
            else:
                # Fallback: if tabs provided but yielded nothing, try current /me view
                cur = (self.driver.current_url or '').lower()
                if 'suno.com/me' not in cur:
                    self.driver.get('https://suno.com/me')
                    time.sleep(2)
                self.scroll_to_load_all()
                songs = self.extract_all_songs()
            
            if not songs:
                logger.warning("No songs extracted. Check if you're on the correct page.")
                return output_files
            
            # Filter disliked if requested
            if exclude_disliked:
                before = len(songs)
                songs = [s for s in songs if not s.get('disliked')]
                logger.info(f"Filtered disliked: {before - len(songs)} removed")

            # Step 4: Extract detailed information
            if extract_details:
                songs = self.extract_detailed_info(songs)
            
            # Step 5: Save to requested formats
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if 'md' in save_formats or 'markdown' in save_formats:
                output_files['markdown'] = self.save_to_markdown(
                    songs, f"suno_liked_songs_{timestamp}.md"
                )
            
            if 'json' in save_formats:
                output_files['json'] = self.save_to_json(
                    songs, f"suno_liked_songs_{timestamp}.json"
                )
            
            if 'csv' in save_formats:
                output_files['csv'] = self.save_to_csv(
                    songs, f"suno_liked_songs_{timestamp}.csv"
                )
            
            # Summary
            logger.info("=" * 60)
            logger.info("✓ EXTRACTION COMPLETE")
            logger.info(f"✓ Total songs: {len(songs)}")
            for fmt, path in output_files.items():
                logger.info(f"✓ {fmt.upper()}: {path}")
            logger.info("=" * 60)
            
            return output_files
            
        except ExtractionError:
            # Re-raise our custom exceptions as-is
            raise
        except Exception as e:
            logger.error(f"✗ Extraction failed: {e}", exc_info=True)
            raise ExtractionError(f"Extraction failed: {e}") from e


def main():
    """Main execution with configuration"""
    
    # ========== CONFIGURATION ==========
    BROWSER = "chrome"  # or "firefox"
    DEBUG_PORT = 9222    # 9222 for Chrome, 9223 for Firefox
    OUTPUT_DIR = "suno_songs"
    EXTRACT_DETAILS = True
    SAVE_FORMATS = ['md', 'json', 'csv']  # Choose formats to export
    # ===================================
    
    print("=" * 70)
    print("🎵 SUNO LIKED SONGS EXTRACTOR - Existing Browser Session")
    print("=" * 70)
    print()
    
    # Initialize extractor
    extractor = SunoExtractor(output_dir=OUTPUT_DIR, browser=BROWSER)
    
    try:
        # Connect to existing browser
        print(f"Connecting to {BROWSER.title()}...")
        print(f"Make sure {BROWSER.title()} is running with debug port {DEBUG_PORT}")
        print()
        
        extractor.connect_to_existing_browser(debug_port=DEBUG_PORT)
        
        # Run extraction
        output_files = extractor.run_extraction(
            extract_details=EXTRACT_DETAILS,
            save_formats=SAVE_FORMATS,
            tabs=['creations'],
            exclude_disliked=True
        )
        
        # Success message
        print("\n" + "=" * 70)
        print("✓ SUCCESS! Your liked songs have been extracted.")
        print(f"✓ Output directory: {OUTPUT_DIR}/")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n✗ Extraction cancelled by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("Check 'suno_extractor.log' for detailed error information")
    finally:
        # Note: We don't close the browser since it was already open
        if extractor.driver:
            logger.info("Disconnecting from browser (keeping it open)...")


if __name__ == "__main__":
    main()
