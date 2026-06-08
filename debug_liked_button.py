#!/usr/bin/env python3
import sys, io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

options = Options()
options.add_experimental_option('debuggerAddress', '127.0.0.1:9222')
driver = webdriver.Chrome(options=options)
print('URL:', driver.current_url)

try:
    el = driver.find_element(By.XPATH, "//button[contains(normalize-space(.), 'Liked')]")
    print('Found Liked button')
    print('  text:', el.text)
    print('  aria-pressed:', el.get_attribute('aria-pressed'))
    print('  aria-selected:', el.get_attribute('aria-selected'))
    print('  class:', el.get_attribute('class'))
    print('  data-state:', el.get_attribute('data-state'))
except Exception as e:
    print('Error:', e)

driver.quit()
