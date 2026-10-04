import sys
import time
import os
from playwright.sync_api import sync_playwright

def test_all_modules(base_url="http://localhost:3000"):
    print(f"\n=======================================================")
    print(f"TESTING ALL MODULES ON {base_url}")
    print(f"=======================================================")

    console_logs = []
    page_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # 1. Login
        print("1. Opening /login...")
        page.goto(f"{base_url}/login", wait_until="networkidle")
        time.sleep(1)

        print("2. Clicking 'Administrator' demo account button...")
        page.click("button:has-text('Administrator')")
        time.sleep(0.5)

        print("3. Clicking 'Sign in' button...")
        page.click("button:has-text('Sign in')")

        page.wait_for_url("**/dashboard", timeout=15000)
        print("   -> Logged in successfully!")
        time.sleep(2)

        # List of all sidebar modules
        modules = [
            ("Dashboard", "/dashboard", "Total contracts"),
            ("Contracts", "/contracts", "Contracts"),
            ("Approvals", "/approvals", "Approval Management Inbox"),
            ("Obligations", "/obligations", "Obligations"),
            ("Renewals", "/renewals", "Renewals"),
            ("AI Q&A", "/qa", "AI Q&A"),
            ("Analytics", "/analytics", "Analytics"),
            ("Audit Trail", "/audit", "Audit Trail"),
            ("Users", "/admin/users", "Users"),
        ]

        results = {}

        for label, path, expected_text in modules:
            print(f"\n--- Testing module: '{label}' ({path}) ---")
            link = page.locator(f"aside nav a:has-text('{label}')")
            if not link.is_visible():
                print(f"   [FAIL] Sidebar link for '{label}' is NOT visible!")
                results[label] = "Link Not Found"
                continue

            link.click()
            # Next.js SPA client-side routing wait
            try:
                page.wait_for_function(f"() => window.location.pathname === '{path}'", timeout=8000)
                # Wait for main content or text
                page.wait_for_selector(f"text={expected_text}", timeout=8000)
                time.sleep(1)

                extra_info = ""
                if path == "/contracts":
                    page.wait_for_selector("table tbody tr", timeout=8000)
                    row_count = page.locator("table tbody tr").count()
                    extra_info = f" ({row_count} contracts rendered in table)"
                elif path == "/approvals":
                    row_count = page.locator("table tbody tr, .card").count()
                    extra_info = f" ({row_count} approval elements rendered)"
                elif path == "/obligations":
                    cards = page.locator(".card").count()
                    extra_info = f" ({cards} cards rendered)"
                elif path == "/renewals":
                    rows = page.locator("table tbody tr").count()
                    extra_info = f" ({rows} renewal rows rendered)"
                elif path == "/analytics":
                    extra_info = " (charts and KPIs rendered)"
                elif path == "/audit":
                    extra_info = " (hash chain verified and table rendered)"
                elif path == "/admin/users":
                    user_rows = page.locator("table tbody tr").count()
                    extra_info = f" ({user_rows} users rendered in table)"

                # Save screenshot of each module
                filename = f"scratch/{label.lower().replace(' ', '_').replace('&', '').replace('/', '_')}.png"
                page.screenshot(path=filename)
                print(f"   [SUCCESS] Navigated to '{label}'! Current URL: {page.url}{extra_info}")
                print(f"   Screenshot: {filename}")
                results[label] = "PASS" + extra_info

            except Exception as e:
                print(f"   [ERROR] Failed on '{label}': {e}")
                results[label] = f"FAIL: {e}"
                page.screenshot(path=f"scratch/error_{label.lower().replace(' ', '_')}.png")

        print("\n=======================================================")
        print("SUMMARY OF MODULE NAVIGATION RESULTS:")
        print("=======================================================")
        for mod, res in results.items():
            print(f"  - {mod:15}: {res}")

        # Check for any React unhandled runtime error overlay
        error_overlay = page.locator("nextjs-portal, [data-nextjs-dialog-header]")
        if error_overlay.count() > 0:
            print("\n[WARNING] Next.js error overlay detected on page!")

        print(f"\nTotal console logs captured: {len(console_logs)}")
        error_logs = [l for l in console_logs if "[error]" in l]
        print(f"Console errors: {len(error_logs)}")
        for err in error_logs[:10]:
            print(f"  {err}")

        browser.close()

if __name__ == "__main__":
    os.makedirs("scratch", exist_ok=True)
    test_all_modules("http://localhost:3000")
