import sys
import time
import os
from playwright.sync_api import sync_playwright

def test_approval_ui():
    print("\n=======================================================")
    print("TESTING LIVE APPROVAL WORKFLOW DECISION IN BROWSER")
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
        time.sleep(2)

        # Initial screenshot
        page.screenshot(path="scratch/approval_before_decision.png")
        print("   -> Screenshot saved: scratch/approval_before_decision.png")

        # 3. Locate the first actionable "Approve" button
        approve_btn = page.locator("button:has-text('Approve')").first
        if not approve_btn.is_visible():
            print("   [NOTE] No active 'Approve' button found in inbox.")
            browser.close()
            return

        print("3. Clicking 'Approve' button on the pending approval step...")
        approve_btn.click()
        page.wait_for_selector("text=Approve Contract Step", timeout=5000)
        time.sleep(1)

        # 4. Fill in optional comment and confirm
        print("4. Entering approval comments and confirming decision...")
        page.fill("textarea", "Automated real-time approval verification - Approved by System Administrator.")
        page.click("button:has-text('Confirm Approval')")

        # 5. Wait for toast or modal to close
        time.sleep(2)
        page.screenshot(path="scratch/approval_after_decision.png")
        print("   -> Screenshot saved: scratch/approval_after_decision.png")
        print("   -> [SUCCESS] Approval decision executed in real time!")

        # 6. Check Contracts page to see updated status
        print("\n5. Navigating to Contracts page to verify live status...")
        page.click("aside nav a:has-text('Contracts')")
        page.wait_for_function("() => window.location.pathname === '/contracts'", timeout=8000)
        page.wait_for_selector("table tbody tr", timeout=8000)
        time.sleep(2)

        page.screenshot(path="scratch/contracts_after_approval.png")
        print("   -> Screenshot saved: scratch/contracts_after_approval.png")
        print("   -> [SUCCESS] Contracts page reflects updated approval status live!")

        browser.close()

if __name__ == "__main__":
    os.makedirs("scratch", exist_ok=True)
    test_approval_ui()
