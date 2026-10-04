"""
Configurable multi-level approval workflow engine.

A workflow definition is a JSON document:
{
    "steps": [
        {"name": "Legal Review", "role": "legal", "sla_hours": 48},
        {"name": "Finance Review", "role": "finance", "sla_hours": 24, "condition": {"min_value": 10000}},
        ...
    ],
    "parallel": false
}

When a contract is submitted for review, the engine creates one Approval
record per step with an SLA deadline. Decisions advance the workflow:
- Approved step → activate the next step (or finalize the contract).
- Rejected step → stop the workflow and mark the contract rejected.
- Changes requested → stop and notify the owner.
- Delegated → reassign to another user (recorded as a separate approval).
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.models import (
    Contract, Approval, ApprovalWorkflow, User, ApprovalDecision,
    ContractStatus, Notification
)


DEFAULT_WORKFLOW = {
    "name": "Default Approval Flow",
    "description": "Standard multi-level approval for low-risk contracts.",
    "definition": {
        "steps": [
            {"name": "Legal Review", "role": "legal", "sla_hours": 48},
            {"name": "Manager Review", "role": "manager", "sla_hours": 48},
            {"name": "Finance Review", "role": "finance", "sla_hours": 24,
             "condition": {"min_value": 10000}},
            {"name": "Compliance Review", "role": "compliance", "sla_hours": 24},
        ],
        "parallel": False,
    },
    "is_default": True,
}


HIGH_VALUE_WORKFLOW = {
    "name": "High-Value Approval Flow",
    "description": "Used for high-value or high-risk contracts.",
    "definition": {
        "steps": [
            {"name": "Legal Review", "role": "legal", "sla_hours": 48},
            {"name": "Manager Review", "role": "manager", "sla_hours": 48},
            {"name": "Finance Review", "role": "finance", "sla_hours": 24},
            {"name": "Compliance Review", "role": "compliance", "sla_hours": 24},
            {"name": "Executive Sign-off", "role": "executive", "sla_hours": 72},
        ],
        "parallel": False,
    },
}


LOW_RISK_WORKFLOW = {
    "name": "Lightweight Flow",
    "description": "Used for low-risk, low-value contracts.",
    "definition": {
        "steps": [
            {"name": "Manager Review", "role": "manager", "sla_hours": 24},
            {"name": "Legal Review", "role": "legal", "sla_hours": 24},
        ],
        "parallel": False,
    },
}


def _matches_condition(step: Dict, contract: Contract) -> bool:
    cond = step.get("condition")
    if not cond:
        return True
    if "min_value" in cond:
        return (contract.value_amount or 0) >= float(cond["min_value"])
    if "max_risk" in cond:
        order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return order.get(contract.risk_level, 0) <= int(cond["max_risk"])
    if "types" in cond:
        return contract.contract_type in cond["types"]
    return True


def _pick_assignee(db: Session, role: str) -> Optional[User]:
    return db.execute(
        select(User).where(User.role == role, User.is_active == True).order_by(User.created_at.asc()).limit(1)
    ).scalar_one_or_none()


def select_workflow_for(db: Session, contract: Contract) -> Optional[ApprovalWorkflow]:
    high_value = (contract.value_amount or 0) >= 100000
    critical = contract.risk_level in ("high", "critical")
    target_def = None
    if critical:
        target_def = HIGH_VALUE_WORKFLOW
    elif high_value:
        target_def = HIGH_VALUE_WORKFLOW
    elif (contract.value_amount or 0) < 5000 and contract.risk_level == "low":
        target_def = LOW_RISK_WORKFLOW
    else:
        target_def = DEFAULT_WORKFLOW

    wf = db.execute(
        select(ApprovalWorkflow).where(ApprovalWorkflow.name == target_def["name"])
    ).scalar_one_or_none()
    return wf


def start_workflow(db: Session, contract: Contract, actor, workflow: Optional[ApprovalWorkflow] = None) -> List[Approval]:
    if not workflow:
        workflow = select_workflow_for(db, contract)
    if not workflow:
        raise ValueError("No workflow available")

    # Clear old workflow steps if re-submitting
    db.query(Approval).filter(Approval.contract_id == contract.id).delete()

    steps: List[Dict] = workflow.definition.get("steps", [])
    approvals: List[Approval] = []
    now = datetime.now(timezone.utc)
    step_counter = 0

    for idx, step in enumerate(steps):
        if not _matches_condition(step, contract):
            continue
        assignee = _pick_assignee(db, step["role"])
        due = now + timedelta(hours=int(step.get("sla_hours", 48)))

        # Step 0 is PENDING, all subsequent steps are NOT_STARTED (LOCKED)
        initial_decision = ApprovalDecision.PENDING.value if step_counter == 0 else ApprovalDecision.NOT_STARTED.value

        ap = Approval(
            contract_id=contract.id,
            workflow_id=workflow.id,
            step_index=step_counter,
            step_name=step["name"],
            required_role=step["role"],
            assignee_id=assignee.id if assignee else None,
            decision=initial_decision,
            sla_hours=int(step.get("sla_hours", 48)),
            due_at=due,
        )
        db.add(ap)
        approvals.append(ap)

        if step_counter == 0 and assignee:
            db.add(Notification(
                user_id=assignee.id,
                title=f"Approval required: {contract.title}",
                body=f"You have been assigned step '{step['name']}' for contract '{contract.title}'. SLA: {step.get('sla_hours', 48)} hours.",
                level="info",
                link=f"/contracts/{contract.id}",
            ))
        step_counter += 1

    contract.status = "pending_approval"
    
    from app.services.status_service import record_status_change
    record_status_change(db, str(contract.id), contract.status, "pending_approval", str(actor.id), "Submitted for approval review")
    db.flush()
    return approvals


def decide(db: Session, approval: Approval, actor, decision: str, comments: Optional[str]) -> Contract:
    contract = approval.contract

    if decision not in {d.value for d in ApprovalDecision}:
        raise ValueError(f"Unknown decision: {decision}")

    # 1. Enforce active step status
    if approval.decision == ApprovalDecision.NOT_STARTED.value:
        raise PermissionError("Previous approval steps must be completed first.")

    # 2. Enforce sequential step order - verify all previous steps are APPROVED or SKIPPED
    prev_steps = db.query(Approval).filter(
        Approval.contract_id == contract.id,
        Approval.step_index < approval.step_index
    ).all()
    for prev in prev_steps:
        if prev.decision not in {ApprovalDecision.APPROVED.value, ApprovalDecision.SKIPPED.value}:
            raise PermissionError("Previous approval steps must be completed first.")

    # 3. Enforce user authorization
    if actor.role != "admin" and actor.role != approval.required_role:
        if actor.id != approval.assignee_id:
            raise PermissionError("You are not authorized to decide this step.")

    now = datetime.now(timezone.utc)
    approval.decision = decision
    approval.comments = comments
    approval.decided_at = now

    from app.services.status_service import record_status_change

    if decision == ApprovalDecision.REJECTED.value:
        contract.status = ContractStatus.REJECTED.value
        record_status_change(db, str(contract.id), "pending_approval", ContractStatus.REJECTED.value, str(actor.id), f"Rejected at step '{approval.step_name}'")
        db.flush()
        return contract

    if decision == ApprovalDecision.CHANGES_REQUESTED.value:
        contract.status = "changes_requested"
        record_status_change(db, str(contract.id), "pending_approval", "changes_requested", str(actor.id), f"Changes requested at step '{approval.step_name}'")
        db.flush()
        return contract

    if decision == ApprovalDecision.SKIPPED.value or decision == ApprovalDecision.APPROVED.value:
        # Find next locked step (NOT_STARTED or PENDING)
        next_step = db.query(Approval).filter(
            Approval.contract_id == contract.id,
            Approval.step_index > approval.step_index
        ).order_by(Approval.step_index.asc()).first()

        if next_step:
            # Activate next step
            next_step.decision = ApprovalDecision.PENDING.value
            next_step.due_at = now + timedelta(hours=next_step.sla_hours)
            if next_step.assignee_id:
                db.add(Notification(
                    user_id=next_step.assignee_id,
                    title=f"Approval required: {contract.title}",
                    body=f"Step '{next_step.step_name}' is now active for contract '{contract.title}'.",
                    level="info",
                    link=f"/contracts/{contract.id}",
                ))
            db.flush()
            return contract

    # All steps completed!
    contract.status = ContractStatus.APPROVED.value
    record_status_change(db, str(contract.id), "pending_approval", ContractStatus.APPROVED.value, str(actor.id), "All approval steps completed successfully")
    db.flush()
    return contract


def _find_next_pending(db: Session, contract: Contract, after_step_index: int) -> Optional[Approval]:
    return db.execute(
        select(Approval)
        .where(Approval.contract_id == contract.id,
               Approval.step_index > after_step_index,
               Approval.decision == ApprovalDecision.PENDING.value)
        .order_by(Approval.step_index.asc())
        .limit(1)
    ).scalar_one_or_none()


def activate_after_approval(db: Session, contract: Contract):
    if contract.status == ContractStatus.APPROVED.value:
        old_status = contract.status
        contract.status = ContractStatus.ACTIVE.value
        from app.services.status_service import record_status_change
        record_status_change(db, str(contract.id), old_status, ContractStatus.ACTIVE.value, reason="Contract executed & activated")
        db.flush()
