import sys
import os
sys.path.append(os.path.abspath("backend"))

from app.db.session import SessionLocal
from app.models.models import Contract, Approval, User

db = SessionLocal()
contracts = db.query(Contract).order_by(Contract.created_at.desc()).all()
print(f"Total contracts: {len(contracts)}\n")

for i, c in enumerate(contracts, 1):
    approvals = db.query(Approval).filter(Approval.contract_id == c.id).order_by(Approval.step_index).all()
    app_list = [f"{a.step_name} ({a.decision})" for a in approvals]
    app_summary = ", ".join(app_list) if app_list else "None"
    print(f"{i}. [{c.contract_number}] \"{c.title}\"")
    print(f"   Status: {c.status} | Type: {c.contract_type} | Risk: {c.risk_level} ({c.risk_score})")
    print(f"   Approvals: {app_summary}")
    print()

# Check what /approvals/inbox returns
admin_user = db.query(User).filter(User.email == "admin@acme.io").first()
pending_approvals = db.query(Approval).filter(Approval.decision == "pending").all()
print(f"\n--- Total pending approval steps in DB: {len(pending_approvals)} ---")
for pa in pending_approvals:
    c = db.query(Contract).filter(Contract.id == pa.contract_id).first()
    print(f" - Step: '{pa.step_name}' for Contract: '{c.title}' (Contract Status: {c.status})")

db.close()
