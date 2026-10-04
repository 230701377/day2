from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user, require_role
from app.models.models import User, ContractTemplate
from app.schemas.schemas import WorkflowOut
from pydantic import BaseModel

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    name: str
    contract_type: str
    body: str
    required_clauses: List[str] = []
    recommended_clauses: List[str] = []
    description: str = ""


class TemplateOut(BaseModel):
    id: str
    name: str
    contract_type: str
    body: str
    required_clauses: List[str]
    recommended_clauses: List[str]
    description: str
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[TemplateOut])
def list_templates(db: Session = Depends(get_db),
                    actor: User = Depends(get_current_user)):
    rows = db.query(ContractTemplate).order_by(ContractTemplate.name.asc()).all()
    return rows


@router.post("", response_model=TemplateOut)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db),
                     actor: User = Depends(require_role("admin", "legal"))):
    t = ContractTemplate(
        name=payload.name, contract_type=payload.contract_type,
        body=payload.body, required_clauses=payload.required_clauses,
        recommended_clauses=payload.recommended_clauses,
        description=payload.description,
    )
    db.add(t)
    db.flush()
    from app.services.audit.chain import append as audit_append
    audit_append(db, actor=actor, action="template.create",
                 resource_type="template", resource_id=str(t.id),
                 payload={"name": t.name, "type": t.contract_type})
    db.commit()
    db.refresh(t)
    return t
