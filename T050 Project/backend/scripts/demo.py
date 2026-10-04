"""Demo runner: starts the API, opens the browser, and prints a guided walkthrough.

Usage: python scripts/demo.py
"""
import os
import sys
import time
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.models import User, Contract
from app.core.security import hash_password


def main():
    db = SessionLocal()
    try:
        print("=" * 72)
        print("Contract Lifecycle & Approval Management - Demo")
        print("=" * 72)
        print()
        print("Service URLs:")
        print("  - Frontend:  http://localhost:3000")
        print("  - Backend:   http://localhost:8000/api/v1/docs")
        print("  - Health:    http://localhost:8000/health")
        print()
        print("Demo accounts (password 'Demo1234!'):")
        for u in db.query(User).order_by(User.role).all():
            print(f"  - {u.email:30s} role={u.role}")
        print()
        print("Seeded contracts:")
        for c in db.query(Contract).order_by(Contract.title).all():
            print(f"  - {c.title[:60]:60s} risk={c.risk_level} status={c.status}")
        print()
        print("Suggested demo flow:")
        print("  1. Sign in as requester@acme.io")
        print("  2. Open the 'Quantum Logistics (HIGH RISK)' contract")
        print("  3. Click 'AI analyze' to see clause extraction and risk detection")
        print("  4. Click the Q&A tab and ask: 'What is the liability cap?'")
        print("  5. Submit for review, then sign in as legal@acme.io and approve")
        print("  6. Check the Audit Trail page to see the hash-chained log")
        print("  7. Visit Analytics for portfolio dashboards")
        print()
    finally:
        db.close()
    try:
        webbrowser.open("http://localhost:3000")
    except Exception:
        pass


if __name__ == "__main__":
    main()
