"""Tamper-evident audit log using a SHA-256 hash chain.

Each row contains the SHA-256 of (sequence || timestamp || actor || action ||
resource_type || resource_id || payload_json || previous_hash). Any tampering
breaks the chain.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.models import AuditLog


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash_entry(sequence: int, ts: datetime, actor_id: Optional[str],
                actor_email: Optional[str], action: str,
                resource_type: Optional[str], resource_id: Optional[str],
                payload: Any, previous_hash: str) -> str:
    blob = "|".join([
        str(sequence),
        ts.astimezone(timezone.utc).isoformat(),
        str(actor_id or ""),
        str(actor_email or ""),
        str(action),
        str(resource_type or ""),
        str(resource_id or ""),
        _canonical(payload),
        previous_hash,
    ]).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def next_sequence(db: Session) -> int:
    last = db.execute(select(AuditLog).order_by(AuditLog.sequence.desc()).limit(1)).scalar_one_or_none()
    return (last.sequence + 1) if last else 1


def append(db: Session, *, actor, action: str, resource_type: Optional[str] = None,
           resource_id: Optional[str] = None, payload: Optional[Dict[str, Any]] = None,
           ip_address: Optional[str] = None, user_agent: Optional[str] = None,
           commit: bool = True) -> AuditLog:
    payload = payload or {}
    last = db.execute(select(AuditLog).order_by(AuditLog.sequence.desc()).limit(1)).scalar_one_or_none()
    seq = (last.sequence + 1) if last else 1
    prev_hash = last.entry_hash if last else "0" * 64
    ts = datetime.now(timezone.utc)
    actor_id = str(getattr(actor, "id", None)) if actor else None
    actor_email = getattr(actor, "email", None) if actor else None
    digest = _hash_entry(seq, ts, actor_id, actor_email, action,
                          resource_type, resource_id, payload, prev_hash)
    entry = AuditLog(
        sequence=seq,
        timestamp=ts,
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        payload=payload,
        previous_hash=prev_hash,
        entry_hash=digest,
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry


def verify_chain(db: Session) -> Dict[str, Any]:
    rows = db.execute(select(AuditLog).order_by(AuditLog.sequence.asc())).scalars().all()
    prev = "0" * 64
    expected_seq = 1
    for row in rows:
        if row.sequence != expected_seq:
            return {"valid": False, "broken_at_sequence": row.sequence,
                    "total_entries": len(rows),
                    "message": f"Sequence gap detected at {row.sequence} (expected {expected_seq})."}
        digest = _hash_entry(row.sequence, row.timestamp, str(row.actor_id) if row.actor_id else None,
                              row.actor_email, row.action, row.resource_type, row.resource_id,
                              row.payload, prev)
        if digest != row.entry_hash or row.previous_hash != prev:
            return {"valid": False, "broken_at_sequence": row.sequence,
                    "total_entries": len(rows),
                    "message": "Hash chain integrity violation detected."}
        prev = row.entry_hash
        expected_seq += 1
    return {"valid": True, "total_entries": len(rows),
            "message": "Audit log hash chain is intact."}
