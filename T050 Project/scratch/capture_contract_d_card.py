from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    page.goto('http://localhost:3000/login', wait_until='networkidle')
    page.click("button:has-text('Administrator')")
    page.click("button:has-text('Sign in')")
    page.wait_for_url('**/dashboard', timeout=12000)
    page.goto('http://localhost:3000/approvals', wait_until='networkidle')
    time.sleep(3)
    
    # Scroll to Contract D card
    d_card = page.locator(".card:has-text('Contract D - Consulting Agreement')").first
    d_card.scroll_into_view_if_needed()
    time.sleep(1)
    page.screenshot(path='scratch/approvals_contract_d_scrolled.png')
    print('Saved scratch/approvals_contract_d_scrolled.png')
    browser.close()
