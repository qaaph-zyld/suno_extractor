#!/usr/bin/env python3
import io, sys, re, time
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

options = Options()
options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
driver = webdriver.Chrome(options=options)

url = "https://suno.com/song/43a18ea4-d1ae-40b4-8245-e9ee8c7b6c82"
print("Loading %s..." % url)
driver.get(url)
time.sleep(3)

print("URL after load:", driver.current_url)

# Click lyrics tab
try:
    for btn in driver.find_elements(By.XPATH, "//button[contains(normalize-space(.), 'Lyrics')]"):
        if btn.is_displayed():
            print("Clicking lyrics button:", btn.text)
            btn.click()
            time.sleep(1)
            break
except Exception as e:
    print("No lyrics button:", e)

soup = BeautifulSoup(driver.page_source, "lxml")

# Try all lyrics selectors
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

print("Lyrics length:", len(lyrics))
print("Lyrics preview:", lyrics[:200] if lyrics else "NONE")

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

print("Description:", description[:200] if description else "NONE")

driver.quit()
