#!/usr/bin/env python3
"""Test history page navigation"""

from playwright.sync_api import sync_playwright
import time

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})

        # Navigate to the frontend
        page.goto('http://localhost:3000')
        time.sleep(3)

        # Click on history link
        page.click('text=历史记录')
        time.sleep(3)

        # Take screenshot of history page
        page.screenshot(path='/home/yarizakurahime/data/dairy_supply_chain_risk/screenshot_history.png', full_page=True)
        print("History page screenshot saved")

        # Check for 404
        if page.locator('text=404').count() > 0 or page.locator('text=This page could not be found').count() > 0:
            print("ERROR: 404 found on history page")
        else:
            print("OK: History page loaded successfully")

        browser.close()

if __name__ == '__main__':
    main()
