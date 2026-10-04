# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width': 1400, 'height': 900})
    page.goto('http://localhost:3000/login', wait_until='networkidle')
    page.click("button:has-text('Administrator')")
    page.click("button:has-text('Sign in')")
    page.wait_for_url('**/dashboard', timeout=12000)
    
    page.goto('http://localhost:3000/renewals', wait_until='networkidle')
    time.sleep(2)
    
    # Click first Renew button in table row
    print('Clicking first Renew button in table row...')
    renew_btn = page.locator("tbody tr button:has-text('Renew')").first
    renew_btn.click()
    time.sleep(1)
    
    # Take screenshot of the modal
    page.screenshot(path='scratch/renewals_modal_open.png')
    print('Saved scratch/renewals_modal_open.png')
    
    # Click confirm renewal
    print('Confirming renewal...')
    page.click("button:has-text('Confirm & Create Renewal')")
    time.sleep(3)
    
    # Screenshot after renewal creation
    page.screenshot(path='scratch/renewals_after_confirmed.png')
    print('Saved scratch/renewals_after_confirmed.png')
    browser.close()
