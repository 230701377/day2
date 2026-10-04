from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    page.goto('http://localhost:3000/login', wait_until='networkidle')
    page.click("button:has-text('Administrator')")
    page.click("button:has-text('Sign in')")
    page.wait_for_url('**/dashboard', timeout=12000)
    page.goto('http://localhost:3000/contracts/1486d6c1-e1bc-439f-a3d7-8b8d337bb22a', wait_until='networkidle')
    time.sleep(2)
    page.screenshot(path='scratch/contract_d_empty_state.png')
    print('Screenshot saved successfully!')
    browser.close()
