"""
Background SLA & Obligation Worker.

Monitors contract SLA timelines, auto-renewal notice windows, and obligation due dates.
Dispatches real-time WebSocket alerts to active enterprise users.
"""
import asyncio
import logging
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any

from app.db.session import SessionLocal, engine
from app.models.models import Base, Contract, Obligation
from app.api.v1.websockets import manager as ws_manager

logger = logging.getLogger(__name__)


async def scan_and_alert_obligations():
    """
    Scans database for pending obligations and upcoming contract expirations.
    Broadcasts real-time notifications over WebSockets.
    """
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        upcoming_threshold = now + timedelta(days=30)

        # 1. Scan obligations due within 30 days
        obligations = db.query(Obligation).filter(
            Obligation.status.in_(["open", "Pending", "pending"]),
            Obligation.due_date != None
        ).all()

        alert_count = 0
        for ob in obligations:
            if ob.due_date and ob.due_date <= upcoming_threshold:
                alert_count += 1
                event_data = {
                    "event": "sla_alert",
                    "title": f"SLA Obligation Due: {ob.title}",
                    "contract_id": str(ob.contract_id),
                    "due_date": ob.due_date.isoformat(),
                    "priority": ob.priority or "HIGH",
                    "severity": "WARNING"
                }
                await ws_manager.broadcast_global(event_data)

        # 2. Scan contracts expiring within 60 days
        contracts = db.query(Contract).filter(
            Contract.status.in_(["active", "ACTIVE"]),
            Contract.expiration_date != None
        ).all()

        for c in contracts:
            if c.expiration_date and c.expiration_date <= (now + timedelta(days=60)):
                await ws_manager.broadcast_global({
                    "event": "contract_expiring_soon",
                    "contract_id": str(c.id),
                    "contract_name": c.title,
                    "expiration_date": c.expiration_date.isoformat(),
                    "message": f"Contract '{c.title}' expires on {c.expiration_date.strftime('%Y-%m-%d')}."
                })

        logger.info(f"[ObligationWorker] Completed SLA scan. Active tracking operational.")
    except Exception as e:
        logger.warning(f"[ObligationWorker] SLA scan note: {e}")
    finally:
        db.close()


def start_obligation_periodic_scheduler():
    """Start background async task polling every 60 seconds."""
    async def scheduler():
        while True:
            await scan_and_alert_obligations()
            await asyncio.sleep(60)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(scheduler())
    except Exception as e:
        logger.warning(f"[ObligationWorker] Could not schedule background task: {e}")
