#!/usr/bin/env python3
"""Capture screenshot of the dairy supply chain risk frontend"""

from playwright.sync_api import sync_playwright
import time

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})

        # Navigate to the frontend (try ports in reverse order - latest first)
        for port in [3009, 3008, 3007, 3006, 3005, 3004, 3003, 3002, 3001, 3000]:
            try:
                page.goto(f'http://localhost:{port}', timeout=5000)
                print(f"Connected to frontend on port {port}")
                break
            except:
                continue
        else:
            raise Exception("Could not connect to frontend on any port")
        # Wait for content to load instead of networkidle
        time.sleep(4)

        # Wait longer for demo cases to load from API
        print("Waiting for demo cases to load...")
        time.sleep(5)  # Increased wait time for API call

        # Take screenshot to see current state
        page.screenshot(path='/home/yarizakurahime/data/dairy_supply_chain_risk/screenshot_check.png', full_page=True)

        try:
            # Wait for either loaded content or timeout
            page.wait_for_selector('text=历史案例库', timeout=15000)
            print("History case library loaded")
        except:
            print("Timeout waiting for history case library, continuing anyway")

        time.sleep(2)  # Extra wait for API call to complete

        # Take initial screenshot
        page.screenshot(path='/home/yarizakurahime/data/dairy_supply_chain_risk/screenshot_1_initial.png', full_page=True)
        print("Screenshot 1 saved: initial state")

        # Instead of relying on demo cases loading, directly test with a query
        print("\nTesting direct query input...")

        # Find the search input and enter a query
        try:
            # Look for input placeholder
            page.fill('input[placeholder*="企业"], input[placeholder*="批次"]', '莫斯利安')
            print("Entered query: 莫斯利安")
            time.sleep(1)

            # Click the search button (开始研判)
            page.click('button:has-text("开始研判")')
            print("Clicked 开始研判 button")

            # Wait for assessment to complete (longer wait for full workflow)
            print("Waiting for assessment to complete...")
            time.sleep(15)

            page.screenshot(path='/home/yarizakurahime/data/dairy_supply_chain_risk/screenshot_2_completed.png', full_page=True)
            print("Screenshot 2 saved: assessment completed")
        except Exception as e:
            print(f"Could not interact with search: {e}")

        # Check if demo cases are visible
        demo_buttons = page.locator('button:has-text("运行研判")').all()
        print(f"Found {len(demo_buttons)} '运行研判' buttons")

        if len(demo_buttons) > 0:
            # Click the first demo case
            demo_buttons[0].click()
            print("Clicked first demo case")

            # Wait for streaming workflow to appear
            time.sleep(3)

            # Take screenshot after clicking
            page.screenshot(path='/home/yarizakurahime/data/dairy_supply_chain_risk/screenshot_2_streaming.png', full_page=True)
            print("Screenshot 2 saved: streaming state")

            # Wait a bit more for steps to complete
            time.sleep(4)

            # Take final screenshot
            page.screenshot(path='/home/yarizakurahime/data/dairy_supply_chain_risk/screenshot_3_complete.png', full_page=True)
            print("Screenshot 3 saved: completed state")

            # Check for workflow steps component
            workflow_text = page.locator('text=研判流程').count()
            print(f"Workflow component visible: {workflow_text > 0}")

        # Test demo cases if they loaded
        demo_buttons = page.locator('button:has-text("运行研判")').all()
        print(f"\nFound {len(demo_buttons)} demo case buttons")

        if len(demo_buttons) > 0:
            print("Testing demo case click...")
            demo_buttons[0].click()
            time.sleep(15)
            page.screenshot(path='/home/yarizakurahime/data/dairy_supply_chain_risk/screenshot_3_demo_case.png', full_page=True)
            print("Screenshot 3 saved: demo case completed")
        else:
            print("Demo cases didn't load - checking if API is accessible...")
            # Navigate to API directly to verify
            page.goto('http://localhost:8000/demo_cases')
            time.sleep(2)
            content = page.content()
            if 'target_hint' in content:
                print("API is returning target_hint correctly")
            else:
                print("API response issue")

        browser.close()

if __name__ == '__main__':
    main()
