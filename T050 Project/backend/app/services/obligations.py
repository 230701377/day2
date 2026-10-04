"""Obligation extraction and renewal alert computation."""
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

from app.models.models import Clause, Obligation


OBLIGATION_PATTERNS = [
    (re.compile(r"(\w+)\s+shall\s+(pay|provide|deliver|notify|submit|maintain|renew|file|report|train|audit|insure|comply|register)\b[^.]{5,300}", re.IGNORECASE), "obligation"),
    (re.compile(r"(\w+)\s+(must|will|agrees? to|undertakes? to|is required to)\s+(pay|provide|deliver|notify|submit|maintain|renew|file|report|train|audit|insure|comply|register)\b[^.]{5,300}", re.IGNORECASE), "obligation"),
    (re.compile(r"on or before\s+([A-Z][a-z]+\s+\d{1,2},\s*\d{4}|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})", re.IGNORECASE), "deadline"),
    (re.compile(r"due\s+(?:on|by)?\s*([A-Z][a-z]+\s+\d{1,2},\s*\d{4}|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})", re.IGNORECASE), "deadline"),
    (re.compile(r"every\s+(\d+)\s+(day|week|month|quarter|year)s?", re.IGNORECASE), "recurrence"),
]


def _infer_priority(text: str) -> str:
    text = text.lower()
    if any(w in text for w in ["immediately", "critical", "essential", "material breach"]):
        return "high"
    if any(w in text for w in ["annual", "quarterly", "monthly", "recurring"]):
        return "medium"
    return "medium"


def _extract_titles(body: str) -> List[str]:
    titles = []
    for pat, _ in OBLIGATION_PATTERNS[:2]:
        for m in pat.finditer(body):
            t = m.group(0).strip()
            if 12 < len(t) < 280:
                titles.append(t)
    return titles[:8]


def _extract_deadlines(body: str) -> List[str]:
    out = []
    for pat, _ in OBLIGATION_PATTERNS[1:4]:
        for m in pat.finditer(body):
            out.append(m.group(1))
    return out[:5]


def extract_obligations_from_clauses(clauses) -> List[Dict]:
    """Return dicts describing candidate obligations.

    Accepts a list of either SQLAlchemy Clause objects or plain dicts with
    the same keys.
    """
    out: List[Dict] = []
    for c in clauses:
        if isinstance(c, dict):
            body = c.get("body", "")
            category = c.get("category")
            cid = c.get("id")
            page = c.get("page_number")
        else:
            body = getattr(c, "body", "")
            category = getattr(c, "category", None)
            cid = getattr(c, "id", None)
            page = getattr(c, "page_number", None)
        titles = _extract_titles(body)
        deadlines = _extract_deadlines(body)
        for t in titles:
            out.append({
                "title": t[:200],
                "description": (body[:300] + ("..." if len(body) > 300 else "")),
                "category": category,
                "due_date_text": deadlines[0] if deadlines else None,
                "source_clause_id": cid,
                "source_page": page,
                "priority": _infer_priority(t),
            })
    return out


def compute_renewal_alerts(contract, today: Optional[datetime] = None) -> Optional[Dict]:
    if not contract.expiration_date:
        return None
    today = today or datetime.now(timezone.utc)
    notice = contract.renewal_notice_days or 60
    days_left = (contract.expiration_date - today).days
    return {
        "contract_id": str(contract.id),
        "contract_number": contract.contract_number,
        "title": contract.title,
        "counterparty": contract.counterparty,
        "contract_type": contract.contract_type,
        "department": contract.department,
        "value_amount": contract.value_amount,
        "value_currency": contract.value_currency or "USD",
        "risk_level": contract.risk_level or "low",
        "risk_score": contract.risk_score or 0.0,
        "status": contract.status,
        "effective_date": contract.effective_date,
        "expiration_date": contract.expiration_date,
        "days_until_expiry": days_left,
        "auto_renew": contract.auto_renew,
        "renewal_notice_days": notice,
        "notice_deadline": contract.expiration_date - timedelta(days=notice),
        "action_required": days_left <= notice,
    }
