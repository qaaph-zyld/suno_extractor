#!/usr/bin/env python3
import sys, io, time
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

options = Options()
options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
driver = webdriver.Chrome(options=options)

print("Current URL:", driver.current_url)

# Navigate to likes page
if "suno.com/me" not in driver.current_url:
    driver.get("https://suno.com/me")
    time.sleep(3)

# Click Liked tab
for xp in ["//button[contains(normalize-space(.), 'Liked')]", "//a[contains(normalize-space(.), 'Liked')]"]:
    try:
        el = driver.find_element(By.XPATH, xp)
        if el.is_displayed():
            cls = (el.get_attribute("class") or "").lower()
            if "bg-foreground-primary" in cls:
                print("Liked tab already active")
            else:
                el.click()
                print("Clicked Liked tab")
            time.sleep(2)
            break
    except Exception:
        pass

print("Final URL:", driver.current_url)
driver.quit()
