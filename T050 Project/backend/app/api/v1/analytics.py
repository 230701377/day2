from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, select, or_

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.models import (
    User, Contract, Approval, ApprovalDecision, Obligation, RiskFinding, ContractStatus
)
from app.schemas.schemas import (
    AnalyticsOverview, RiskDistribution, ContractByType,
    BottleneckStep, ApprovalTimelinePoint,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _scope_query(q, actor: User):
    if actor.role == "requester":
        return q.filter(Contract.owner_id == actor.id)
    return q


@router.get("/overview", response_model=AnalyticsOverview)
def overview(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    cq = _scope_query(db.query(Contract), actor)
    now = datetime.now(timezone.utc)
    horizon_30d = now + timedelta(days=30)
    horizon_60d = now + timedelta(days=60)

    total_contracts = cq.count()
    draft = cq.filter(Contract.status == "draft").count()
    processing = cq.filter(or_(Contract.status.in_(["processing", "queued"]), Contract.processing_status.in_(["PROCESSING", "QUEUED"]))).count()
    ready_for_review = cq.filter(Contract.status.in_(["analysis_complete", "in_review"])).count()
    pending_approvals = cq.filter(Contract.status == "pending_approval").count()
    approved = cq.filter(Contract.status == "approved").count()
    active_contracts = cq.filter(Contract.status == ContractStatus.ACTIVE.value).count()
    rejected = cq.filter(Contract.status == ContractStatus.REJECTED.value).count()
    changes_requested = cq.filter(Contract.status == "changes_requested").count()
    high_risk = cq.filter(Contract.risk_level.in_(["high", "critical"])).count()
    expiring_soon = cq.filter(
        Contract.expiration_date != None,
        Contract.expiration_date <= horizon_30d,
        Contract.expiration_date >= now
    ).count()
    expired = cq.filter(
        Contract.expiration_date != None,
        Contract.expiration_date < now
    ).count()

    overdue = db.query(Approval).filter(
        Approval.decision == ApprovalDecision.PENDING.value,
        Approval.due_at < now
    ).count()

    obligations_due = cq.join(Obligation, Obligation.contract_id == Contract.id).filter(
        Obligation.due_date != None,
        Obligation.due_date <= horizon_30d,
        Obligation.status != "completed",
    ).count()

    renewals = cq.filter(
        Contract.expiration_date != None,
        Contract.expiration_date <= horizon_60d,
    ).count()

    total_value = cq.with_entities(func.coalesce(func.sum(Contract.value_amount), 0)).scalar() or 0

    return AnalyticsOverview(
        total_contracts=total_contracts,
        draft=draft,
        processing=processing,
        ready_for_review=ready_for_review,
        pending_approval=pending_approvals,
        approved=approved,
        active=active_contracts,
        rejected=rejected,
        changes_requested=changes_requested,
        high_risk=high_risk,
        expiring_soon=expiring_soon,
        expired=expired,
        # Backward compatibility
        active_contracts=active_contracts,
        pending_approvals=pending_approvals,
        overdue_approvals=overdue,
        high_risk_count=high_risk,
        obligations_due_30d=obligations_due,
        renewals_due_60d=renewals,
        total_value=float(total_value),
    )


@router.get("/risk-distribution", response_model=List[RiskDistribution])
def risk_distribution(db: Session = Depends(get_db),
                       actor: User = Depends(get_current_user)):
    cq = _scope_query(db.query(Contract), actor)
    rows = cq.with_entities(Contract.risk_level, func.count(Contract.id))\
        .group_by(Contract.risk_level).all()
    out = [{"level": r[0] or "low", "count": r[1]} for r in rows]
    # ensure all buckets present
    have = {o["level"] for o in out}
    for level in ("low", "medium", "high", "critical"):
        if level not in have:
            out.append({"level": level, "count": 0})
    return out


@router.get("/by-type", response_model=List[ContractByType])
def by_type(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    cq = _scope_query(db.query(Contract), actor)
    rows = cq.with_entities(Contract.contract_type, func.count(Contract.id))\
        .group_by(Contract.contract_type).all()
    return [{"contract_type": r[0], "count": r[1]} for r in rows]


@router.get("/bottlenecks", response_model=List[BottleneckStep])
def bottlenecks(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    # average duration between step assignment and decision
    decided = db.query(Approval).filter(Approval.decided_at.isnot(None)).all()
    by_step: dict[str, list[float]] = {}
    pending_counts: dict[str, int] = {}
    for ap in decided:
        if ap.created_at and ap.decided_at:
            hours = (ap.decided_at - ap.created_at).total_seconds() / 3600.0
            by_step.setdefault(ap.step_name, []).append(hours)
    pending = db.query(Approval).filter(Approval.decision == ApprovalDecision.PENDING.value).all()
    for ap in pending:
        pending_counts[ap.step_name] = pending_counts.get(ap.step_name, 0) + 1
    out = []
    for step, hours in by_step.items():
        avg = sum(hours) / len(hours)
        out.append({
            "step_name": step,
            "average_hours": round(avg, 2),
            "pending_count": pending_counts.get(step, 0),
        })
    out.sort(key=lambda x: x["average_hours"], reverse=True)
    return out


@router.get("/approval-timeline", response_model=List[ApprovalTimelinePoint])
def approval_timeline(db: Session = Depends(get_db),
                       actor: User = Depends(get_current_user),
                       days: int = 30):
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    approved = db.query(Approval).filter(Approval.decided_at.isnot(None)).all()
    buckets: dict[str, dict[str, int]] = {}
    for d in range(days + 1):
        day = (start + timedelta(days=d)).isoformat()
        buckets[day] = {"submitted": 0, "approved": 0, "rejected": 0}
    for ap in approved:
        if not ap.decided_at:
            continue
        day = ap.decided_at.date().isoformat()
        if day not in buckets:
            continue
        if ap.decision == ApprovalDecision.APPROVED.value:
            buckets[day]["approved"] += 1
        elif ap.decision == ApprovalDecision.REJECTED.value:
            buckets[day]["rejected"] += 1
    submitted = db.query(Approval).all()
    for ap in submitted:
        day = ap.created_at.date().isoformat()
        if day in buckets:
            buckets[day]["submitted"] += 1
    out = []
    for day in sorted(buckets.keys()):
        out.append(ApprovalTimelinePoint(date=day, **buckets[day]))
    return out


@router.get("/obligations-summary")
def obligations_summary(db: Session = Depends(get_db),
                         actor: User = Depends(get_current_user)):
    cq = _scope_query(db.query(Contract), actor)
    q = cq.join(Obligation, Obligation.contract_id == Contract.id)
    by_status = q.with_entities(Obligation.status, func.count(Obligation.id))\
        .group_by(Obligation.status).all()
    by_priority = q.with_entities(Obligation.priority, func.count(Obligation.id))\
        .group_by(Obligation.priority).all()
    return {
        "by_status": [{"status": s, "count": c} for s, c in by_status],
        "by_priority": [{"priority": p, "count": c} for p, c in by_priority],
    }


@router.get("/risk-trend")
def risk_trend(db: Session = Depends(get_db),
                actor: User = Depends(get_current_user),
                days: int = 30):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    rows = db.query(RiskFinding).filter(RiskFinding.created_at >= start).all()
    by_day: dict[str, dict[str, int]] = {}
    for r in rows:
        d = r.created_at.date().isoformat()
        by_day.setdefault(d, {"low": 0, "medium": 0, "high": 0, "critical": 0})
        by_day[d][r.severity] = by_day[d].get(r.severity, 0) + 1
    out = []
    for d in sorted(by_day.keys()):
        out.append({"date": d, **by_day[d]})
    return out


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    """
    Comprehensive live Enterprise Dashboard summary API.
    Calculated directly from actual database records.
    """
    from app.models.models import AuditLog
    cq = _scope_query(db.query(Contract), actor)
    now = datetime.now(timezone.utc)
    
    total_contracts = cq.count()
    draft_count = cq.filter(Contract.status == "draft").count()
    processing_count = cq.filter(or_(Contract.status.in_(["processing", "queued"]), Contract.processing_status.in_(["PROCESSING", "QUEUED"]))).count()
    ready_for_review_count = cq.filter(Contract.status.in_(["analysis_complete", "in_review"])).count()
    pending_approval_count = cq.filter(Contract.status == "pending_approval").count()
    pending_approvals_count = pending_approval_count
    approved_count = cq.filter(Contract.status == "approved").count()
    active_contracts = cq.filter(Contract.status == ContractStatus.ACTIVE.value).count()
    rejected_count = cq.filter(Contract.status == ContractStatus.REJECTED.value).count()
    changes_requested_count = cq.filter(Contract.status == "changes_requested").count()
    high_risk_count = cq.filter(Contract.risk_level.in_(["high", "critical"])).count()
    
    horizon_30d = now + timedelta(days=30)
    horizon_60d = now + timedelta(days=60)

    expiring_soon_count = cq.filter(
        Contract.expiration_date != None,
        Contract.expiration_date <= horizon_30d,
        Contract.expiration_date >= now
    ).count()

    expired_count = cq.filter(
        Contract.expiration_date != None,
        Contract.expiration_date < now
    ).count()

    renewals_due_60d = cq.filter(
        Contract.expiration_date != None,
        Contract.expiration_date <= horizon_60d
    ).count()

    try:
        obligations_due_30d = cq.join(Obligation, Obligation.contract_id == Contract.id).filter(
            Obligation.due_date != None,
            Obligation.due_date <= horizon_30d,
            Obligation.status != "completed"
        ).count()
    except Exception:
        obligations_due_30d = 0

    needs_human_review_count = cq.filter(
        (Contract.risk_score >= 80) | (Contract.status == "in_review") | (Contract.contract_type == "other")
    ).count()

    # Contract types breakdown
    type_rows = cq.with_entities(Contract.contract_type, func.count(Contract.id)).group_by(Contract.contract_type).all()
    type_dict = {"vendor": 0, "supplier": 0, "customer": 0, "business_partner": 0, "other": 0, "needs_review": 0}
    for t_name, count in type_rows:
        if t_name in type_dict:
            type_dict[t_name] = count
        elif t_name in ("nda", "msa", "sow", "employment", "lease", "license", "service"):
            type_dict["other"] += count
        else:
            type_dict["needs_review"] += count

    # Risk distribution breakdown
    risk_rows = cq.with_entities(Contract.risk_level, func.count(Contract.id)).group_by(Contract.risk_level).all()
    risk_dict = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for r_level, count in risk_rows:
        if r_level in risk_dict:
            risk_dict[r_level] = count
        else:
            risk_dict["low"] += count

    # AI Processing Breakdown
    ai_processing = {
        "processed": total_contracts,
        "processing": 0,
        "needs_review": needs_human_review_count,
        "failed": 0
    }

    # Needs Attention actionable alerts
    needs_attention = []
    if pending_approvals_count > 0:
        needs_attention.append({
            "id": "pending_approvals",
            "title": f"{pending_approvals_count} contract(s) awaiting approval decision",
            "severity": "warning",
            "action_url": "/approvals",
            "type": "approval"
        })
    if needs_human_review_count > 0:
        needs_attention.append({
            "id": "human_review",
            "title": f"{needs_human_review_count} contract(s) require legal classification or review",
            "severity": "info",
            "action_url": "/contracts?status=in_review",
            "type": "review"
        })
    if high_risk_count > 0:
        needs_attention.append({
            "id": "high_risk",
            "title": f"{high_risk_count} high or critical risk contract(s) detected",
            "severity": "danger",
            "action_url": "/contracts?risk=high",
            "type": "risk"
        })
    if expiring_soon_count > 0:
        needs_attention.append({
            "id": "expiring_soon",
            "title": f"{expiring_soon_count} contract(s) expiring within 30 days",
            "severity": "warning",
            "action_url": "/renewals",
            "type": "renewal"
        })

    # Recent contracts
    recent_c_objs = cq.order_by(Contract.updated_at.desc()).limit(6).all()
    recent_contracts = []
    for c in recent_c_objs:
        recent_contracts.append({
            "id": str(c.id),
            "title": c.title,
            "contract_number": c.contract_number,
            "contract_type": c.contract_type,
            "counterparty": c.counterparty or "—",
            "status": c.status,
            "risk_level": c.risk_level,
            "risk_score": c.risk_score,
            "value_amount": c.value_amount,
            "value_currency": c.value_currency,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None
        })

    # Approval Inbox
    inbox_objs = db.query(Approval).filter(Approval.decision == ApprovalDecision.PENDING.value).limit(6).all()
    approval_inbox = []
    for a in inbox_objs:
        c = db.query(Contract).filter(Contract.id == a.contract_id).first()
        approval_inbox.append({
            "id": str(a.id),
            "contract_id": str(a.contract_id),
            "contract_title": c.title if c else "Unknown Contract",
            "contract_type": c.contract_type if c else "nda",
            "risk_level": c.risk_level if c else "low",
            "step_name": a.step_name,
            "step_index": a.step_index,
            "required_role": a.required_role,
            "due_at": a.due_at.isoformat() if a.due_at else None,
            "created_at": a.created_at.isoformat() if a.created_at else None
        })

    # Approval Bottlenecks
    bottlenecks_data = bottlenecks(db=db, actor=actor)

    # Upcoming Renewals
    renewal_c_objs = cq.filter(Contract.expiration_date != None).order_by(Contract.expiration_date.asc()).limit(6).all()
    upcoming_renewals = []
    for c in renewal_c_objs:
        days_rem = (c.expiration_date.date() - now.date()).days if c.expiration_date else 999
        category = "Critical" if days_rem <= 7 else "Urgent" if days_rem <= 30 else "Upcoming" if days_rem <= 60 else "Future"
        upcoming_renewals.append({
            "contract_id": str(c.id),
            "title": c.title,
            "contract_type": c.contract_type,
            "expiration_date": c.expiration_date.isoformat() if c.expiration_date else None,
            "days_remaining": days_rem,
            "category": category,
            "auto_renew": c.auto_renew,
            "notice_period_days": c.renewal_notice_days or 30
        })

    # Recent AI Findings
    findings_objs = db.query(RiskFinding).order_by(RiskFinding.created_at.desc()).limit(6).all()
    recent_ai_findings = []
    for f in findings_objs:
        c = db.query(Contract).filter(Contract.id == f.contract_id).first()
        recent_ai_findings.append({
            "id": str(f.id),
            "contract_id": str(f.contract_id),
            "contract_title": c.title if c else "Contract",
            "finding": f.title or f.description,
            "category": getattr(f, "finding_type", "General"),
            "severity": f.severity,
            "confidence": getattr(f, "score_total", 0.0),
            "page_number": getattr(f, "source_page", 1) or 1,
            "created_at": f.created_at.isoformat() if f.created_at else None
        })

    # Recent Audit Activity
    logs_objs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(8).all()
    recent_activity = []
    for log in logs_objs:
        recent_activity.append({
            "id": str(log.id),
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "actor_id": str(log.actor_id) if log.actor_id else None,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "payload": log.payload
        })

    # Monthly Activity
    monthly_activity = approval_timeline(db=db, actor=actor, days=30)

    return {
        "total_contracts": total_contracts,
        "draft": draft_count,
        "processing": processing_count,
        "ready_for_review": ready_for_review_count,
        "pending_approval": pending_approval_count,
        "approved": approved_count,
        "active": active_contracts,
        "rejected": rejected_count,
        "changes_requested": changes_requested_count,
        "high_risk": high_risk_count,
        "expiring_soon": expiring_soon_count,
        "expired": expired_count,
        "active_contracts": active_contracts,
        "pending_approvals": pending_approval_count,
        "high_risk_contracts": high_risk_count,
        "obligations_due_30_days": obligations_due_30d,
        "renewals_due_60_days": renewals_due_60d,
        "expiring_soon": expiring_soon_count,
        "needs_human_review": needs_human_review_count,
        "contract_types": type_dict,
        "risk_distribution": risk_dict,
        "ai_processing": ai_processing,
        "needs_attention": needs_attention,
        "recent_contracts": recent_contracts,
        "approval_inbox": approval_inbox,
        "approval_bottlenecks": bottlenecks_data,
        "upcoming_renewals": upcoming_renewals,
        "recent_ai_findings": recent_ai_findings,
        "recent_activity": recent_activity,
        "monthly_activity": monthly_activity,
        "last_updated": now.isoformat()
    }
