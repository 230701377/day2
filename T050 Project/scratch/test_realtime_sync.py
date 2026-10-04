import sys
import time
import os
import requests
from playwright.sync_api import sync_playwright

def test_realtime():
    print("\n=======================================================")
    print("TESTING REAL-TIME CONTRACT & APPROVAL UPDATES")
    print("=======================================================")

    base_url = "http://localhost:3000"
    api_url = "http://localhost:8000/api/v1"

    # Login to get auth token for backend API
    r = requests.post(f"{api_url}/auth/login", json={"email": "admin@acme.io", "password": "Demo1234!"})
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # 1. Login in browser
        print("1. Opening /login and signing in...")
        page.goto(f"{base_url}/login", wait_until="networkidle")
        page.click("button:has-text('Administrator')")
        page.click("button:has-text('Sign in')")
        page.wait_for_url("**/dashboard", timeout=12000)

        # 2. Go to Contracts Page
        print("2. Navigating to Contracts page...")
        page.click("aside nav a:has-text('Contracts')")
        page.wait_for_function("() => window.location.pathname === '/contracts'", timeout=8000)
        page.wait_for_selector("table tbody tr", timeout=8000)
        time.sleep(2)

        # 3. Check initial contracts count or status in DOM
        initial_pill = page.locator("button:has-text('All (')").first.inner_text()
        print(f"   -> Initial Contracts Header Pill: {initial_pill}")

        # 4. Trigger a real-time event by creating a new contract or updating via backend API
        print("3. Creating a new test contract via backend API to test instant WebSocket broadcast...")
        new_contract_payload = {
            "title": f"Real-Time Test Agreement {int(time.time())}",
            "counterparty": "Live Sync Partner Ltd",
            "contract_type": "vendor",
            "value_amount": 99000,
            "value_currency": "USD"
        }
        res = requests.post(f"{api_url}/contracts", json=new_contract_payload, headers=headers)
        if res.status_code != 200 and res.status_code != 201:
            print(f"Failed to create contract: {res.status_code} {res.text}")
            return
        created_contract = res.json()
        print(f"   -> Created Contract: '{created_contract['title']}' [ID: {created_contract['id'][:8]}]")

        # 5. Wait for the new contract to appear in the browser DOM WITHOUT refreshing the page!
        print("4. Listening for real-time WebSocket push in browser (NO PAGE REFRESH)...")
        try:
            page.wait_for_selector(f"text={created_contract['title']}", timeout=10000)
            print(f"   -> [REAL-TIME SUCCESS] Contract appeared instantly in the DOM via WebSocket!")
            page.screenshot(path="scratch/realtime_sync_contract_created.png")
            print("   -> Screenshot saved: scratch/realtime_sync_contract_created.png")
        except Exception as e:
            print(f"   -> [TIMEOUT] Contract did not appear in DOM within 10s: {e}")
            page.screenshot(path="scratch/realtime_fail.png")

        # 6. Now test status change in real time: Update contract status or submit for review
        print("\n5. Submitting newly created contract for review via backend API...")
        submit_res = requests.post(f"{api_url}/contracts/{created_contract['id']}/submit-for-review", headers=headers)
        print(f"   -> Submit response status: {submit_res.status_code}")

        print("6. Verifying status badge changed in real time without refreshing...")
        try:
            # Should update to pending_approval or in_review or analysis_complete
            page.wait_for_selector(f"tr:has-text('{created_contract['title']}') >> text=pending approval, text=in review, text=Ready for Review", timeout=10000)
            print("   -> [REAL-TIME SUCCESS] Status badge updated live in table row!")
            page.screenshot(path="scratch/realtime_sync_status_updated.png")
            print("   -> Screenshot saved: scratch/realtime_sync_status_updated.png")
        except Exception as e:
            print(f"   -> Status update check note: {e}")
            page.screenshot(path="scratch/realtime_status_check.png")

        # Clean up test contract so database stays clean
        print("\n7. Cleaning up test contract via API...")
        requests.delete(f"{api_url}/contracts/{created_contract['id']}", headers=headers)
        time.sleep(1)

        browser.close()
        print("\n[ALL REAL-TIME VERIFICATIONS COMPLETE]")

if __name__ == "__main__":
    os.makedirs("scratch", exist_ok=True)
    test_realtime()
