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
    
    # Check total contract cards
    cards = page.locator(".card:has-text('Approval Workflow Progress')")
    print(f'Total Approval Cards: {cards.count()}')
    
    # Check Contract D card
    d_card = page.locator(".card:has-text('Contract D - Consulting Agreement')")
    print(f'Found Contract D Card: {d_card.count() > 0}')
    if d_card.count() > 0:
        print('Contract D Card Text preview:')
        print(d_card.first.inner_text())
        
    page.screenshot(path='scratch/approvals_contract_d_live.png')
    print('Saved scratch/approvals_contract_d_live.png')
    browser.close()
