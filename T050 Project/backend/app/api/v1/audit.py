from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.models import (
    User, AuditLog, Approval, ApprovalDecision, Contract,
    Obligation, RiskFinding,
)
from app.schemas.schemas import (
    AuditOut, AuditVerifyResult, AnalyticsOverview,
    RiskDistribution, ContractByType, BottleneckStep, ApprovalTimelinePoint,
)
from app.services.audit.chain import verify_chain

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=List[AuditOut])
def list_audit(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action: Optional[str] = None,
):
    if actor.role not in {"admin", "legal", "compliance", "executive"}:
        raise HTTPException(status_code=403, detail="Not authorized")
    q = db.query(AuditLog).order_by(AuditLog.sequence.desc())
    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type)
    if resource_id:
        q = q.filter(AuditLog.resource_id == resource_id)
    if action:
        q = q.filter(AuditLog.action == action)
    return q.offset(skip).limit(limit).all()


@router.get("/verify", response_model=AuditVerifyResult)
def verify(db: Session = Depends(get_db),
            actor: User = Depends(get_current_user)):
    if actor.role not in {"admin", "compliance", "executive", "legal"}:
        raise HTTPException(status_code=403, detail="Not authorized")
    res = verify_chain(db)
    return AuditVerifyResult(**res)


@router.get("/contract/{contract_id}")
def contract_trail(contract_id: str, db: Session = Depends(get_db),
                    actor: User = Depends(get_current_user)):
    if actor.role not in {"admin", "legal", "compliance", "executive", "manager"}:
        raise HTTPException(status_code=403, detail="Not authorized")
    rows = db.query(AuditLog).filter(
        AuditLog.resource_id == contract_id
    ).order_by(AuditLog.sequence.asc()).all()
    return rows
