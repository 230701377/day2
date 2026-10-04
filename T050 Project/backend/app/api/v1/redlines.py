"""
API Endpoints for AI Autonomous Redlining.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.models import User, Contract, ContractVersion, Clause
from app.services.ai.redline_service import redline_service

router = APIRouter(prefix="/redlines", tags=["redlines"])


@router.post("/generate/{contract_id}/{version_id}")
def generate_contract_redlines(contract_id: str, version_id: str,
                                db: Session = Depends(get_db),
                                actor: User = Depends(get_current_user)):
    """
    Scans specified contract version clauses and generates AI counter-proposal redlines.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    clauses = db.query(Clause).filter(Clause.version_id == version_id).all()
    if not clauses:
        raise HTTPException(status_code=404, detail="No clauses found for this version")

    clause_dicts = [
        {
            "id": str(c.id),
            "heading": c.heading or c.clause_number,
            "body": c.body,
            "page_number": c.page_number
        }
        for c in clauses
    ]

    results = redline_service.generate_redlines(clause_dicts)

    return {
        "contract_id": contract_id,
        "version_id": version_id,
        "total_redlines": len(results),
        "redlines": results
    }
