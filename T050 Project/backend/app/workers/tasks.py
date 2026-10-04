"""Background tasks."""
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.models import Contract, Approval, Notification, User


def _session() -> Session:
    return SessionLocal()


@celery_app.task(name="app.workers.tasks.renewal_sweep")
def renewal_sweep(days: int = 60):
    """Notify owners when a contract's renewal notice deadline is within `days`."""
    db = _session()
    try:
        now = datetime.now(timezone.utc)
        horizon = now + timedelta(days=days)
        rows = db.query(Contract).filter(
            Contract.expiration_date.isnot(None),
            Contract.expiration_date <= horizon,
        ).all()
        for c in rows:
            notice_due = c.expiration_date - timedelta(days=c.renewal_notice_days or 60)
            if notice_due > now:
                continue
            owner_id = c.owner_id
            existing = db.query(Notification).filter(
                Notification.user_id == owner_id,
                Notification.title.like(f"%{c.title[:30]}%"),
                Notification.link == f"/contracts/{c.id}",
            ).first()
            if existing:
                continue
            db.add(Notification(
                user_id=owner_id,
                title=f"Renewal action required: {c.title}",
                body=(f"Contract expires on {c.expiration_date.strftime('%Y-%m-%d')}. "
                      f"Auto-renew: {c.auto_renew}. Please take action."),
                level="warning",
                link=f"/contracts/{c.id}",
            ))
        db.commit()
        return {"contracts_evaluated": len(rows)}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.approval_overdue_sweep")
def approval_overdue_sweep():
    db = _session()
    try:
        now = datetime.now(timezone.utc)
        rows = db.query(Approval).filter(
            Approval.decision == "pending",
            Approval.due_at < now,
        ).all()
        for ap in rows:
            if not ap.assignee_id:
                continue
            existing = db.query(Notification).filter(
                Notification.user_id == ap.assignee_id,
                Notification.link == f"/contracts/{ap.contract_id}",
                Notification.title.like("%overdue%"),
            ).first()
            if existing:
                continue
            db.add(Notification(
                user_id=ap.assignee_id,
                title=f"Approval overdue: step {ap.step_name}",
                body="This approval step is past its SLA. Please act or escalate.",
                level="error",
                link=f"/contracts/{ap.contract_id}",
            ))
        db.commit()
        return {"overdue": len(rows)}
    finally:
        db.close()
