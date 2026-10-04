"""
Contract Status & Lifecycle Transition Service.

Logs every contract status transition to the contract_status_history table and audit trail.
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.models import ContractStatusHistory


def record_status_change(
    db: Session,
    contract_id: str,
    old_status: Optional[str],
    new_status: str,
    changed_by: Optional[str] = None,
    reason: Optional[str] = None,
) -> ContractStatusHistory:
    """
    Persists a contract status transition entry in the database.
    """
    history = ContractStatusHistory(
        contract_id=contract_id,
        old_status=old_status,
        new_status=new_status,
        changed_by=changed_by,
        reason=reason,
    )
    db.add(history)
    db.flush()
    return history
