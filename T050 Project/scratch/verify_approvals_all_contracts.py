import sys
import time
import os
from playwright.sync_api import sync_playwright

def verify_approvals_all():
    print("\n=======================================================")
    print("VERIFYING APPROVALS PAGE RENDERS ALL CONTRACTS")
    print("=======================================================")

    base_url = "http://localhost:3000"

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # 1. Login
        print("1. Opening /login and signing in as Administrator...")
        page.goto(f"{base_url}/login", wait_until="networkidle")
        page.click("button:has-text('Administrator')")
        page.click("button:has-text('Sign in')")
        page.wait_for_url("**/dashboard", timeout=12000)

        # 2. Go to Approvals Page
        print("2. Navigating to Approvals page...")
        page.click("aside nav a:has-text('Approvals')")
        page.wait_for_function("() => window.location.pathname === '/approvals'", timeout=8000)
        page.wait_for_selector("text=Approval Management Inbox", timeout=8000)
        time.sleep(3)

        # 3. Count contract cards rendered on Approvals page
        cards = page.locator(".card:has-text('Approval Workflow Progress')")
        card_count = cards.count()
        print(f"\n[VERIFICATION] Contract Approval Cards rendered: {card_count}")

        # Screenshot of the page showing all contracts
        page.screenshot(path="scratch/approvals_all_contracts.png")
        print("Screenshot saved to: scratch/approvals_all_contracts.png")

        # Scroll down to capture more cards
        page.evaluate("window.scrollBy(0, 800)")
        time.sleep(1)
        page.screenshot(path="scratch/approvals_all_contracts_scrolled.png")
        print("Screenshot saved to: scratch/approvals_all_contracts_scrolled.png")

        # 4. Test clicking 'Pending Approval' filter
        print("\n3. Testing 'Pending Approval' filter tab...")
        page.click("button:has-text('Pending Approval')")
        time.sleep(1.5)
        pending_count = page.locator(".card:has-text('Approval Workflow Progress')").count()
        print(f"   -> Pending Approval contracts shown: {pending_count}")

        # 5. Test clicking 'Approved' filter
        print("4. Testing 'Approved' filter tab...")
        page.click("button:has-text('Approved')")
        time.sleep(1.5)
        approved_count = page.locator(".card:has-text('Approval Workflow Progress')").count()
        print(f"   -> Approved contracts shown: {approved_count}")

        # 6. Test clicking back to 'All Contracts'
        print("5. Testing 'All Contracts' filter tab...")
        page.click("button:has-text('All Contracts')")
        time.sleep(1.5)
        all_count = page.locator(".card:has-text('Approval Workflow Progress')").count()
        print(f"   -> All Contracts restored: {all_count}")

        browser.close()
        print("\n[VERIFICATION COMPLETE]")

if __name__ == "__main__":
    os.makedirs("scratch", exist_ok=True)
    verify_approvals_all()
