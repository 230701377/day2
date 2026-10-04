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
    
    # 1. Verify Rejected button does not exist
    rejected_buttons = page.locator("button:has-text('Rejected')")
    print(f'Rejected filter buttons found: {rejected_buttons.count()}')
    assert rejected_buttons.count() == 0, 'Rejected tab button should not be present!'
    
    # 2. Check all rendered cards for rejected status
    cards = page.locator(".card:has-text('Approval Workflow Progress')")
    total_cards = cards.count()
    print(f'Total cards on Approvals page: {total_cards}')
    
    rejected_badges = page.locator("span:text-is('rejected')")
    print(f'Rejected badges found: {rejected_badges.count()}')
    assert rejected_badges.count() == 0, 'No rejected contract should appear on the Approvals page!'
    
    page.screenshot(path='scratch/approvals_no_rejected.png')
    print('Screenshot saved to scratch/approvals_no_rejected.png')
    print('VERIFICATION SUCCESSFUL: Rejected contracts are completely hidden from Approvals page!')
    browser.close()
