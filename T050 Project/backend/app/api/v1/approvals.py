from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.models import User, Contract, Approval, ApprovalDecision, ContractStatus
from app.schemas.schemas import ApprovalOut, ApprovalDecisionRequest, WorkflowCreate, WorkflowOut
from app.services.workflow.engine import decide, start_workflow, select_workflow_for, _matches_condition
from app.services.workflow.engine import DEFAULT_WORKFLOW, HIGH_VALUE_WORKFLOW, LOW_RISK_WORKFLOW
from app.services.audit.chain import append as audit_append

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _enrich_approval(ap: Approval) -> dict:
    d = {
        "id": str(ap.id),
        "contract_id": str(ap.contract_id),
        "workflow_id": str(ap.workflow_id),
        "step_index": ap.step_index,
        "step_name": ap.step_name,
        "required_role": ap.required_role,
        "assignee_id": str(ap.assignee_id) if ap.assignee_id else None,
        "decision": ap.decision,
        "comments": ap.comments,
        "sla_hours": ap.sla_hours,
        "due_at": ap.due_at,
        "decided_at": ap.decided_at,
        "created_at": ap.created_at,
    }
    if ap.contract:
        c = ap.contract
        d.update({
            "contract_title": c.title,
            "contract_number": c.contract_number,
            "counterparty": c.counterparty,
            "contract_type": c.contract_type,
            "value_amount": c.value_amount,
            "value_currency": c.value_currency,
            "risk_level": c.risk_level,
            "risk_score": c.risk_score,
        })
    return d


@router.get("/inbox", response_model=List[ApprovalOut])
def inbox(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    """Pending approvals assigned to or actionable by the current user."""
    q = db.query(Approval).filter(Approval.decision == ApprovalDecision.PENDING.value)
    if actor.role != "admin":
        q = q.filter((Approval.assignee_id == actor.id) | (Approval.required_role == actor.role))
    approvals = q.order_by(Approval.due_at.asc()).all()
    return [_enrich_approval(a) for a in approvals]


@router.get("/contract/{contract_id}", response_model=List[ApprovalOut])
def contract_approvals(contract_id: str, db: Session = Depends(get_db),
                        actor: User = Depends(get_current_user)):
    approvals = db.query(Approval).filter(Approval.contract_id == contract_id).order_by(
        Approval.step_index.asc()).all()
    if approvals:
        return [_enrich_approval(a) for a in approvals]

    # If no approval rows in DB yet, return expected workflow definition steps
    c = db.query(Contract).filter(Contract.id == contract_id).first()
    if not c:
        return []

    wf = select_workflow_for(db, c)
    steps = wf.definition.get("steps", []) if (wf and wf.definition) else DEFAULT_WORKFLOW["definition"]["steps"]
    results = []
    step_counter = 0
    for s in steps:
        if not _matches_condition(s, c):
            continue
        results.append({
            "id": f"step-{c.id}-{step_counter}",
            "contract_id": str(c.id),
            "workflow_id": str(wf.id) if wf else "default-wf",
            "step_index": step_counter,
            "step_name": s.get("name", "Review Step"),
            "required_role": s.get("role", "legal"),
            "assignee_id": None,
            "decision": "not_started",
            "comments": None,
            "sla_hours": int(s.get("sla_hours", 48)),
            "due_at": None,
            "decided_at": None,
            "created_at": None,
            "contract_title": c.title,
            "contract_number": c.contract_number,
            "counterparty": c.counterparty,
            "contract_type": c.contract_type,
            "value_amount": c.value_amount,
            "value_currency": c.value_currency,
            "risk_level": c.risk_level,
            "risk_score": c.risk_score,
        })
        step_counter += 1
    return results


@router.post("/{approval_id}/decide", response_model=ApprovalOut)
@router.post("/{approval_id}/approve")
@router.post("/{approval_id}/reject")
@router.post("/{approval_id}/request-changes")
def decide_approval(approval_id: str, payload: ApprovalDecisionRequest = None,
                     db: Session = Depends(get_db),
                     actor: User = Depends(get_current_user)):
    ap = db.query(Approval).filter(Approval.id == approval_id).first()
    if not ap:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    if ap.decision in {ApprovalDecision.APPROVED.value, ApprovalDecision.REJECTED.value, ApprovalDecision.CHANGES_REQUESTED.value}:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "error": "ALREADY_DECIDED",
            "message": "Approval step has already been completed."
        })

    if ap.decision in {ApprovalDecision.NOT_STARTED.value, "locked"}:
        # Find previous unapproved step to report name in error message
        prev_step = db.query(Approval).filter(
            Approval.contract_id == ap.contract_id,
            Approval.step_index < ap.step_index,
            Approval.decision != ApprovalDecision.APPROVED.value
        ).order_by(Approval.step_index.asc()).first()
        prev_name = prev_step.step_name if prev_step else "previous step"

        raise HTTPException(status_code=409, detail={
            "success": False,
            "error": "STEP_LOCKED",
            "message": f"Step '{prev_name}' must be approved before '{ap.step_name}'."
        })

    decision_val = payload.decision if payload and payload.decision else ApprovalDecision.APPROVED.value
    comments_val = payload.comments if payload else None

    try:
        contract = decide(db, ap, actor, decision_val, comments_val)
    except PermissionError as pe:
        raise HTTPException(status_code=409, detail={
            "success": False,
            "error": "STEP_LOCKED",
            "message": str(pe)
        })
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    audit_append(db, actor=actor, action=f"approval.{decision_val}", resource_type="approval",
                 resource_id=str(ap.id),
                 payload={"decision": decision_val, "comments": comments_val,
                          "contract_id": str(ap.contract_id)})
    db.commit()
    db.refresh(ap)

    try:
        from sqlalchemy.orm import selectinload
        from app.api.v1.contracts import _enrich_contract_out
        from app.api.v1.websockets import dispatch_global_event
        c = db.query(Contract).options(selectinload(Contract.approvals)).filter(Contract.id == ap.contract_id).first()
        if c:
            enriched = _enrich_contract_out(c)
            contract_dict = enriched.model_dump(mode="json")
            dispatch_global_event({
                "event": "approval_updated",
                "table": "approvals",
                "type": "UPDATE",
                "contract_id": str(c.id),
                "approval_id": str(ap.id),
                "step_name": ap.step_name,
                "decision": decision_val,
                "contract": contract_dict,
            })
            dispatch_global_event({
                "event": "contract_updated",
                "table": "contracts",
                "type": "UPDATE",
                "data": contract_dict,
                "contract_id": str(c.id),
            })
    except Exception:
        pass

    return _enrich_approval(ap)


@router.get("/workflows", response_model=List[WorkflowOut])
def list_workflows(db: Session = Depends(get_db),
                    actor: User = Depends(get_current_user)):
    return db.query(ApprovalWorkflow).order_by(ApprovalWorkflow.name.asc()).all()


@router.post("/workflows", response_model=WorkflowOut)
def create_workflow(payload: WorkflowCreate, db: Session = Depends(get_db),
                     actor: User = Depends(get_current_user)):
    if actor.role not in {"admin", "legal"}:
        raise HTTPException(status_code=403, detail="Admin or legal only")
    wf = ApprovalWorkflow(name=payload.name, description=payload.description,
                          definition=payload.definition, is_default=payload.is_default or False)
    db.add(wf)
    db.flush()
    audit_append(db, actor=actor, action="workflow.create", resource_type="workflow",
                 resource_id=str(wf.id), payload={"name": wf.name})
    db.commit()
    db.refresh(wf)
    return wf


@router.post("/workflows/seed-defaults")
def seed_defaults(db: Session = Depends(get_db),
                   actor: User = Depends(get_current_user)):
    if actor.role not in {"admin", "legal"}:
        raise HTTPException(status_code=403, detail="Admin or legal only")
    added = []
    for cfg in [DEFAULT_WORKFLOW, HIGH_VALUE_WORKFLOW, LOW_RISK_WORKFLOW]:
        if not db.query(ApprovalWorkflow).filter(ApprovalWorkflow.name == cfg["name"]).first():
            wf = ApprovalWorkflow(**cfg)
            db.add(wf)
            db.flush()
            added.append(wf.name)
    audit_append(db, actor=actor, action="workflow.seed", payload={"added": added})
    db.commit()
    return {"added": added}
