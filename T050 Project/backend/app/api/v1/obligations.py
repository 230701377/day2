from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.models import User, Contract, Obligation
from app.schemas.schemas import ObligationOut, ObligationComplete
from app.services.obligations import compute_renewal_alerts
from app.services.audit.chain import append as audit_append

router = APIRouter(prefix="/obligations", tags=["obligations"])


@router.get("", response_model=List[ObligationOut])
def list_obligations(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    status: Optional[str] = None,
    contract_id: Optional[str] = None,
    owner_id: Optional[str] = None,
):
    q = db.query(Obligation)
    if actor.role == "requester":
        # requesters see obligations for contracts they own
        owned = db.query(Contract.id).filter(Contract.owner_id == actor.id).subquery()
        q = q.filter(Obligation.contract_id.in_(owned))
    if status:
        q = q.filter(Obligation.status == status)
    if contract_id:
        q = q.filter(Obligation.contract_id == contract_id)
    if owner_id:
        q = q.filter(Obligation.owner_id == owner_id)
    return q.order_by(Obligation.due_date.asc().nullslast()).all()


@router.post("/{obligation_id}/complete", response_model=ObligationOut)
def complete_obligation(obligation_id: str, payload: ObligationComplete,
                         db: Session = Depends(get_db),
                         actor: User = Depends(get_current_user)):
    ob = db.query(Obligation).filter(Obligation.id == obligation_id).first()
    if not ob:
        raise HTTPException(status_code=404, detail="Obligation not found")
    ob.status = "completed"
    ob.last_completed_at = datetime.now(timezone.utc)
    ob.recurrence_count = (ob.recurrence_count or 0) + 1
    if ob.owner_id is None:
        ob.owner_id = actor.id
    db.flush()
    audit_append(db, actor=actor, action="obligation.complete", resource_type="obligation",
                 resource_id=str(ob.id), payload=payload.model_dump())
    db.commit()
    db.refresh(ob)
    return ob


@router.post("/{obligation_id}/assign")
def assign_obligation(obligation_id: str, user_id: str,
                       db: Session = Depends(get_db),
                       actor: User = Depends(get_current_user)):
    ob = db.query(Obligation).filter(Obligation.id == obligation_id).first()
    if not ob:
        raise HTTPException(status_code=404, detail="Obligation not found")
    ob.owner_id = user_id
    db.flush()
    audit_append(db, actor=actor, action="obligation.assign", resource_type="obligation",
                 resource_id=str(ob.id), payload={"assignee": user_id})
    db.commit()
    return {"obligation_id": str(ob.id), "assignee_id": user_id}


@router.get("/renewals")
def upcoming_renewals(db: Session = Depends(get_db),
                       actor: User = Depends(get_current_user),
                       days: int = 365):
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=days)
    q = db.query(Contract).filter(
        Contract.expiration_date.isnot(None),
        Contract.expiration_date <= horizon,
        Contract.status != "rejected",
    )
    if actor.role == "requester":
        q = q.filter(Contract.owner_id == actor.id)
    alerts = []
    for c in q.all():
        a = compute_renewal_alerts(c, today=now)
        if a:
            alerts.append(a)
    alerts.sort(key=lambda x: x["days_until_expiry"])
    return alerts
