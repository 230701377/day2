import sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, ".")

from app.db.session import SessionLocal
from app.models.models import Contract

def main():
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    
    # Exclude rejected or deleted contracts
    contracts = db.query(Contract).filter(Contract.status != "rejected").order_by(Contract.created_at.asc()).all()
    print(f"Setting expiration & renewal dates for {len(contracts)} contracts...")
    
    # Schedule offsets: (days_until_expiry, renewal_notice_days, auto_renew)
    schedule = [
        (18, 30, True),    # Action Required: notice overdue by 12 days, auto-renews!
        (25, 30, True),    # Action Required: notice overdue by 5 days, auto-renews!
        (35, 30, False),   # Urgent: notice due in 5 days
        (48, 45, True),    # 30-90d: notice due in 3 days, auto-renews
        (65, 60, True),    # 30-90d: notice due in 5 days, auto-renews
        (82, 60, False),   # 30-90d: notice due in 22 days
        (110, 60, True),   # 90-180d: notice due in 50 days, auto-renews
        (135, 60, False),  # 90-180d
        (160, 90, True),   # 90-180d
        (210, 60, False),  # >180d
        (275, 90, True),   # >180d
        (340, 60, False),  # >180d
    ]
    
    for idx, c in enumerate(contracts):
        config = schedule[idx % len(schedule)]
        days_exp, notice_days, auto_renew = config
        
        c.effective_date = now - timedelta(days=365 - days_exp)
        c.expiration_date = now + timedelta(days=days_exp)
        c.renewal_notice_days = notice_days
        c.auto_renew = auto_renew
        
        print(f"[{c.contract_number}] {c.title} -> Expires in {days_exp}d | Notice: {notice_days}d | Auto-renew: {auto_renew}")
        
    db.commit()
    print("All renewal dates successfully assigned!")

if __name__ == "__main__":
    main()
