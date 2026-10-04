import io
import re
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, Query, BackgroundTasks
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, or_, and_

from app.db.session import get_db
from app.api.deps import get_current_user, require_role, client_ip
from app.models.models import (
    User, Contract, ContractVersion, Clause, ContractMetadata, RiskFinding,
    ContractStatus, ApprovalWorkflow, Approval, ApprovalDecision, RiskLevel
)
from app.schemas.schemas import (
    ContractCreate, ContractUpdate, ContractOut, VersionOut, ClauseOut,
    RiskOut, AnalysisOut, VersionDiffOut, ProcessingStatusOut, ApprovalStepSummary
)
from app.services.storage import get_storage, sha256_bytes, sha256_stream
from app.services.parser import parse_document
from app.services.ai.clauses import extract_clauses, classify_clauses_batch
from app.services.ai.embeddings import encode, fit_corpus
from app.services.ai.risk import detect_risks, overall_risk_score
from app.services.ai.llm import summarize_heuristic, extract_metadata_heuristic
from app.services.ai.compare import compare_versions
from app.services.obligations import extract_obligations_from_clauses, compute_renewal_alerts
from app.services.audit.chain import append as audit_append
from app.services.workflow.engine import start_workflow, select_workflow_for
from app.api.v1.websockets import dispatch_global_event

router = APIRouter(prefix="/contracts", tags=["contracts"])


def _gen_contract_number() -> str:
    return f"CT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"


def _enrich_contract_out(c: Contract) -> ContractOut:
    steps: List[ApprovalStepSummary] = []
    current_step = None
    if getattr(c, "approvals", None):
        sorted_apps = sorted(c.approvals, key=lambda a: a.step_index)
        for a in sorted_apps:
            steps.append(ApprovalStepSummary(
                id=str(a.id),
                step_index=a.step_index,
                step_name=a.step_name,
                required_role=a.required_role,
                decision=a.decision,
                sla_hours=a.sla_hours or 48,
                due_at=a.due_at,
                decided_at=a.decided_at,
            ))
            if a.decision == "pending" and not current_step:
                current_step = a.step_name

    if not current_step:
        if c.status == "approved":
            current_step = "Approved"
        elif c.status == "active":
            current_step = "Active"
        elif c.status == "rejected":
            current_step = "Rejected"
        elif c.status == "changes_requested":
            current_step = "Changes Requested"
        elif c.status == "draft":
            current_step = "Draft"
        elif c.status == "analysis_complete":
            current_step = "Ready for Review"
        elif c.status == "in_review":
            current_step = "In Review"
        elif c.status == "pending_approval":
            current_step = "Pending Approval"
        else:
            current_step = (c.status or "").replace("_", " ").title()

    c_out = ContractOut.model_validate(c)
    c_out.approval_steps = steps
    c_out.current_approval_step = current_step
    return c_out


def _user_can_view(user: User, contract: Contract) -> bool:
    if user.role == "admin":
        return True
    if user.role == "requester":
        return contract.owner_id == user.id
    return user.role in {"legal", "finance", "manager", "compliance", "executive"}


@router.post("", response_model=ContractOut, status_code=status.HTTP_201_CREATED)
def create_contract(payload: ContractCreate, db: Session = Depends(get_db),
                     actor: User = Depends(get_current_user)):

    # Check for Duplicate Contract Title or Counterparty in Repository
    from app.services.duplicate_service import duplicate_service
    dup_res = duplicate_service.detect_duplicates_in_db(
        db,
        new_title=payload.title,
        new_counterparty=payload.counterparty or "",
        threshold=0.90
    )

    if dup_res.get("has_duplicate") and dup_res.get("matches"):
        top = dup_res["matches"][0]
        raise HTTPException(
            status_code=400,
            detail=f"DUPLICATE CONTRACT BLOCKED: A contract titled '{top['matched_contract_name']}' ({top['matched_contract_number']}) already exists in repository."
        )

    contract = Contract(
        title=payload.title,
        contract_number=_gen_contract_number(),
        contract_type=payload.contract_type,
        counterparty=payload.counterparty,
        department=payload.department,
        value_amount=payload.value_amount,
        value_currency=payload.value_currency or "USD",
        effective_date=payload.effective_date,
        expiration_date=payload.expiration_date,
        auto_renew=payload.auto_renew or False,
        renewal_notice_days=payload.renewal_notice_days or 60,
        description=payload.description,
        tags=payload.tags or [],
        template_id=payload.template_id,
        parent_contract_id=payload.parent_contract_id,
        owner_id=actor.id,
        status=ContractStatus.DRAFT.value,
        is_amendment=bool(payload.parent_contract_id),
    )
    db.add(contract)
    db.flush()
    audit_append(db, actor=actor, action="contract.create", resource_type="contract",
                 resource_id=str(contract.id),
                 payload={"title": contract.title, "type": contract.contract_type})
    db.commit()
    db.refresh(contract)
    enriched = _enrich_contract_out(contract)
    dispatch_global_event({
        "event": "contract_inserted",
        "table": "contracts",
        "type": "INSERT",
        "data": enriched.model_dump(mode="json"),
        "contract_id": str(contract.id),
    })
    return enriched


@router.post("/cleanup-duplicates")
def cleanup_duplicates(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    """
    Purges redundant duplicate contracts from repository.
    """
    from app.services.duplicate_service import duplicate_service
    res = duplicate_service.cleanup_duplicate_contracts_in_db(db)
    return res


@router.get("", response_model=List[ContractOut])
def list_contracts(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    q: Optional[str] = None,
    status: Optional[str] = None,
    contract_type: Optional[str] = None,
    owner_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    stmt = select(Contract).options(selectinload(Contract.approvals))
    if actor.role == "requester":
        stmt = stmt.where(Contract.owner_id == actor.id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(
            Contract.title.ilike(like),
            Contract.counterparty.ilike(like),
            Contract.contract_number.ilike(like),
        ))
    if status:
        stmt = stmt.where(Contract.status == status)
    if contract_type:
        stmt = stmt.where(Contract.contract_type == contract_type)
    if owner_id:
        stmt = stmt.where(Contract.owner_id == owner_id)
    skip_val = getattr(skip, "default", skip) if hasattr(skip, "default") else skip
    limit_val = getattr(limit, "default", limit) if hasattr(limit, "default") else limit
    stmt = stmt.order_by(Contract.updated_at.desc()).offset(skip_val).limit(limit_val)
    contracts = db.execute(stmt).scalars().all()
    return [_enrich_contract_out(c) for c in contracts]


@router.get("/{contract_id}", response_model=ContractOut)
def get_contract(contract_id: str, db: Session = Depends(get_db),
                  actor: User = Depends(get_current_user)):
    c = db.query(Contract).options(selectinload(Contract.approvals)).filter(Contract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    if not _user_can_view(actor, c):
        raise HTTPException(status_code=403, detail="Not authorized to view this contract")
    return _enrich_contract_out(c)


@router.patch("/{contract_id}", response_model=ContractOut)
def update_contract(contract_id: str, payload: ContractUpdate, db: Session = Depends(get_db),
                     actor: User = Depends(get_current_user)):
    c = db.query(Contract).options(selectinload(Contract.approvals)).filter(Contract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    if actor.role not in {"admin", "legal"} and c.owner_id != actor.id:
        raise HTTPException(status_code=403, detail="Only owner, legal, or admin may edit")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(c, k, v)
    db.flush()
    audit_append(db, actor=actor, action="contract.update", resource_type="contract",
                 resource_id=str(c.id), payload=data)
    db.commit()
    db.refresh(c)
    enriched = _enrich_contract_out(c)
    dispatch_global_event({
        "event": "contract_updated",
        "table": "contracts",
        "type": "UPDATE",
        "data": enriched.model_dump(mode="json"),
        "contract_id": str(c.id),
    })
    return enriched


@router.delete("/{contract_id}", status_code=status.HTTP_200_OK)
def delete_contract(
    contract_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user)
):
    """
    Deletes a contract and all associated versions, clauses, risks, and obligations.
    Permitted for contract owner, legal role, or admin role.
    """
    c = db.query(Contract).filter(Contract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    if actor.role not in {"admin", "legal"} and c.owner_id != actor.id:
        raise HTTPException(status_code=403, detail="Only owner, legal, or admin may delete contracts")

    contract_title = c.title
    db.delete(c)
    audit_append(db, actor=actor, action="contract.delete", resource_type="contract",
                 resource_id=str(contract_id), payload={"title": contract_title})
    db.commit()
    dispatch_global_event({
        "event": "contract_deleted",
        "table": "contracts",
        "type": "DELETE",
        "data": {"id": contract_id},
        "contract_id": contract_id,
    })
    return {"message": f"Contract '{contract_title}' deleted successfully", "id": contract_id}


@router.post("/{contract_id}/versions", response_model=VersionOut,
             status_code=status.HTTP_201_CREATED)
async def upload_version(
    contract_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    version_label: Optional[str] = Form(None),
    force_duplicate: Optional[bool] = Form(False),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    c = db.query(Contract).filter(Contract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    if actor.role not in {"admin", "legal"} and c.owner_id != actor.id:
        raise HTTPException(status_code=403, detail="Only owner, legal, or admin may upload")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file payload")

    # Validate File Extension
    ext = (file.filename or "").split(".")[-1].lower()
    if ext not in {"pdf", "docx", "txt"}:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF, DOCX, or TXT.")

    sha = sha256_bytes(data)
    text, pages, page_text, mime = parse_document(file.filename or "upload", data)

    # Multi-Signal Duplicate Detection Check
    if not force_duplicate:
        from app.services.duplicate_service import duplicate_service
        dup_res = duplicate_service.detect_duplicates_in_db(
            db,
            new_text=text,
            new_filename=file.filename or "",
            new_title=c.title or "",
            sha256_hash=sha,
            current_contract_id=c.id,
            threshold=0.85
        )

        if dup_res.get("has_duplicate") and dup_res.get("matches"):
            top = dup_res["matches"][0]
            raise HTTPException(
                status_code=400,
                detail=f"DUPLICATE CONTRACT BLOCKED ({top['similarity_percentage']} Match): {top['reason']}"
            )

    latest = (db.query(ContractVersion)
                .filter(ContractVersion.contract_id == contract_id)
                .order_by(ContractVersion.version_number.desc())
                .first())
    next_n = (latest.version_number + 1) if latest else 1

    storage_key = f"contracts/{c.id}/v{next_n}_{sha[:10]}_{file.filename}"
    storage = get_storage()
    storage.put(storage_key, data)

    version = ContractVersion(
        contract_id=c.id,
        version_number=next_n,
        version_label=version_label or ("amendment" if next_n > 1 else "initial"),
        storage_key=storage_key,
        original_filename=file.filename,
        mime_type=mime,
        size_bytes=len(data),
        sha256_hash=sha,
        page_count=pages,
        content_text=text,
        created_by=actor.id,
    )
    db.add(version)

    # Set contract processing status to QUEUED and record transition
    old_proc_status = c.processing_status
    c.processing_status = "QUEUED"
    c.processing_step = "Queued for AI Analysis"
    c.processing_progress = 10
    c.processing_error = None
    
    from app.services.status_service import record_status_change
    record_status_change(db, str(c.id), old_proc_status, "UPLOADED", str(actor.id), "Document uploaded")
    db.flush()

    audit_append(db, actor=actor, action="contract.version.upload", resource_type="contract_version",
                 resource_id=str(version.id), payload={"contract_id": str(c.id),
                                                       "version": next_n, "sha256": sha,
                                                       "pages": pages})
    db.commit()
    db.refresh(version)

    # Launch non-blocking background worker
    from app.api.v1.ai import process_contract_background
    background_tasks.add_task(process_contract_background, str(c.id), str(version.id))

    return version


@router.get("/{contract_id}/processing-status", response_model=ProcessingStatusOut)
def get_processing_status(
    contract_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user)
):
    c = db.query(Contract).filter(Contract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    return ProcessingStatusOut(
        contract_id=str(c.id),
        processing_status=c.processing_status or "COMPLETED",
        processing_step=c.processing_step or "Completed",
        processing_progress=c.processing_progress if c.processing_progress is not None else 100,
        processing_error=c.processing_error,
        updated_at=c.updated_at,
    )


@router.post("/{contract_id}/retry-analysis")
def retry_analysis(
    contract_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user)
):
    c = db.query(Contract).filter(Contract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")

    version = (db.query(ContractVersion)
                 .filter(ContractVersion.contract_id == contract_id)
                 .order_by(ContractVersion.version_number.desc())
                 .first())

    if not version:
        raise HTTPException(status_code=400, detail="No document version found to re-analyze")

    c.processing_status = "QUEUED"
    c.processing_step = "Queued for Retry"
    c.processing_progress = 10
    c.processing_error = None
    db.commit()

    from app.api.v1.ai import process_contract_background
    background_tasks.add_task(process_contract_background, str(c.id), str(version.id))

    return {"message": "AI analysis job re-queued successfully", "contract_id": contract_id}


@router.get("/{contract_id}/versions", response_model=List[VersionOut])
def list_versions(contract_id: str, db: Session = Depends(get_db),
                   actor: User = Depends(get_current_user)):
    c = db.query(Contract).filter(Contract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    if not _user_can_view(actor, c):
        raise HTTPException(status_code=403, detail="Not authorized")
    return db.query(ContractVersion).filter(
        ContractVersion.contract_id == contract_id
    ).order_by(ContractVersion.version_number.desc()).all()


@router.get("/{contract_id}/versions/{version_id}", response_model=VersionOut)
def get_version(contract_id: str, version_id: str, db: Session = Depends(get_db),
                 actor: User = Depends(get_current_user)):
    v = db.query(ContractVersion).filter(ContractVersion.id == version_id,
                                          ContractVersion.contract_id == contract_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return v


@router.get("/{contract_id}/versions/{version_id}/download")
def download_version(contract_id: str, version_id: str,
                      db: Session = Depends(get_db),
                      actor: User = Depends(get_current_user)):
    v = db.query(ContractVersion).filter(ContractVersion.id == version_id,
                                          ContractVersion.contract_id == contract_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    storage = get_storage()
    if not storage.exists(v.storage_key):
        raise HTTPException(status_code=410, detail="Underlying file missing from storage")
    data = storage.get(v.storage_key)
    # Verify hash on each download
    recomputed = sha256_bytes(data)
    if recomputed != v.sha256_hash:
        raise HTTPException(status_code=500, detail="Stored file hash mismatch - tampering suspected")
    audit_append(db, actor=actor, action="contract.version.download",
                 resource_type="contract_version", resource_id=str(v.id),
                 payload={"contract_id": str(contract_id)})
    db.commit()
    from fastapi.responses import Response
    return Response(content=data, media_type=v.mime_type or "application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{v.original_filename}"'})


@router.post("/{contract_id}/submit-for-review")
@router.post("/{contract_id}/submit-for-approval")
@router.post("/{contract_id}/submit")
def submit_for_review(contract_id: str, db: Session = Depends(get_db),
                       actor: User = Depends(get_current_user)):
    c = db.query(Contract).filter(Contract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    if actor.id != c.owner_id and actor.role not in {"admin", "legal"}:
        raise HTTPException(status_code=403, detail="Only the owner, legal, or admin may submit")
    
    allowed_statuses = {ContractStatus.DRAFT.value, ContractStatus.REJECTED.value, "analysis_complete", "changes_requested"}
    if c.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Cannot submit a contract in status {c.status}")
    
    # Require at least one version
    has_version = db.query(ContractVersion).filter(ContractVersion.contract_id == c.id).first()
    if not has_version:
        raise HTTPException(status_code=400, detail="Upload a contract version first")

    # Select or create approval workflow
    workflow = select_workflow_for(db, c)
    if not workflow:
        from app.services.workflow.engine import DEFAULT_WORKFLOW
        wf = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.name == DEFAULT_WORKFLOW["name"]).first()
        if not wf:
            wf = ApprovalWorkflow(**DEFAULT_WORKFLOW)
            db.add(wf)
            db.flush()
        workflow = wf

    approvals = start_workflow(db, c, actor, workflow)
    
    from app.services.status_service import record_status_change
    record_status_change(db, str(c.id), c.status, "pending_approval", str(actor.id), "Submitted contract for approval workflow")
    
    audit_append(db, actor=actor, action="contract.submit_for_approval", resource_type="contract",
                 resource_id=str(c.id), payload={"workflow_id": str(workflow.id),
                                                  "approvals_created": len(approvals)})
    db.commit()
    db.refresh(c)
    enriched = _enrich_contract_out(c)
    dispatch_global_event({
        "event": "contract_updated",
        "table": "contracts",
        "type": "UPDATE",
        "data": enriched.model_dump(mode="json"),
        "contract_id": str(c.id),
    })
    dispatch_global_event({
        "event": "approval_updated",
        "table": "approvals",
        "type": "UPDATE",
        "contract_id": str(c.id),
        "contract": enriched.model_dump(mode="json"),
    })
    return {"contract_id": str(c.id), "workflow_id": str(workflow.id), "status": c.status,
            "approvals": [{"id": str(a.id), "step": a.step_name, "role": a.required_role,
                            "decision": a.decision, "due_at": a.due_at.isoformat()} for a in approvals]}


@router.post("/{contract_id}/activate")
def activate_contract(contract_id: str, db: Session = Depends(get_db),
                       actor: User = Depends(get_current_user)):
    c = db.query(Contract).options(selectinload(Contract.approvals)).filter(Contract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    if c.status != ContractStatus.APPROVED.value and actor.role != "admin":
        raise HTTPException(status_code=400, detail="Contract is not approved")
    c.status = ContractStatus.ACTIVE.value
    db.flush()
    audit_append(db, actor=actor, action="contract.activate", resource_type="contract",
                 resource_id=str(c.id))
    db.commit()
    db.refresh(c)
    enriched = _enrich_contract_out(c)
    dispatch_global_event({
        "event": "contract_updated",
        "table": "contracts",
        "type": "UPDATE",
        "data": enriched.model_dump(mode="json"),
        "contract_id": str(c.id),
    })
    return {"contract_id": str(c.id), "status": c.status}


@router.post("/{contract_id}/archive")
def archive_contract(contract_id: str, db: Session = Depends(get_db),
                      actor: User = Depends(get_current_user)):
    c = db.query(Contract).options(selectinload(Contract.approvals)).filter(Contract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contract not found")
    if actor.id != c.owner_id and actor.role not in {"admin", "legal", "compliance"}:
        raise HTTPException(status_code=403, detail="Not authorized")
    c.status = ContractStatus.ARCHIVED.value
    db.flush()
    audit_append(db, actor=actor, action="contract.archive", resource_type="contract",
                 resource_id=str(c.id))
    db.commit()
    db.refresh(c)
    enriched = _enrich_contract_out(c)
    dispatch_global_event({
        "event": "contract_updated",
        "table": "contracts",
        "type": "UPDATE",
        "data": enriched.model_dump(mode="json"),
        "contract_id": str(c.id),
    })
    return {"contract_id": str(c.id), "status": c.status}


@router.post("/{contract_id}/renew", response_model=ContractOut)
def renew_contract(contract_id: str, db: Session = Depends(get_db),
                    actor: User = Depends(get_current_user)):
    parent = db.query(Contract).filter(Contract.id == contract_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Contract not found")
    if actor.id != parent.owner_id and actor.role not in {"admin", "legal", "manager"}:
        raise HTTPException(status_code=403, detail="Not authorized")
    new_contract = Contract(
        title=f"{parent.title} (Renewal)",
        contract_number=_gen_contract_number(),
        contract_type=parent.contract_type,
        counterparty=parent.counterparty,
        department=parent.department,
        value_amount=parent.value_amount,
        value_currency=parent.value_currency,
        effective_date=parent.expiration_date,
        expiration_date=None,
        auto_renew=parent.auto_renew,
        renewal_notice_days=parent.renewal_notice_days,
        description=parent.description,
        tags=parent.tags or [],
        template_id=parent.template_id,
        parent_contract_id=parent.id,
        owner_id=parent.owner_id,
        status=ContractStatus.DRAFT.value,
    )
    parent.status = ContractStatus.RENEWED.value
    db.add(new_contract)
    db.flush()
    audit_append(db, actor=actor, action="contract.renew", resource_type="contract",
                 resource_id=str(new_contract.id),
                 payload={"parent_contract_id": str(parent.id)})
    db.commit()
    db.refresh(new_contract)
    parent_enriched = _enrich_contract_out(parent)
    dispatch_global_event({
        "event": "contract_updated",
        "table": "contracts",
        "type": "UPDATE",
        "data": parent_enriched.model_dump(mode="json"),
        "contract_id": str(parent.id),
    })
    enriched = _enrich_contract_out(new_contract)
    dispatch_global_event({
        "event": "contract_inserted",
        "table": "contracts",
        "type": "INSERT",
        "data": enriched.model_dump(mode="json"),
        "contract_id": str(new_contract.id),
    })
    return enriched


@router.post("/{contract_id}/amendments", response_model=ContractOut,
             status_code=status.HTTP_201_CREATED)
def create_amendment(contract_id: str, payload: ContractCreate,
                      db: Session = Depends(get_db),
                      actor: User = Depends(get_current_user)):
    parent = db.query(Contract).filter(Contract.id == contract_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Contract not found")
    amendment = Contract(
        title=payload.title or f"Amendment to {parent.title}",
        contract_number=_gen_contract_number(),
        contract_type=parent.contract_type,
        counterparty=parent.counterparty,
        department=parent.department,
        value_amount=payload.value_amount if payload.value_amount is not None else parent.value_amount,
        value_currency=payload.value_currency or parent.value_currency,
        effective_date=payload.effective_date,
        expiration_date=payload.expiration_date or parent.expiration_date,
        auto_renew=parent.auto_renew,
        renewal_notice_days=parent.renewal_notice_days,
        description=payload.description,
        tags=payload.tags or parent.tags or [],
        parent_contract_id=parent.id,
        template_id=parent.template_id,
        owner_id=parent.owner_id,
        status=ContractStatus.DRAFT.value,
        is_amendment=True,
    )
    db.add(amendment)
    db.flush()
    audit_append(db, actor=actor, action="contract.amend", resource_type="contract",
                 resource_id=str(amendment.id),
                 payload={"parent_contract_id": str(parent.id)})
    db.commit()
    db.refresh(amendment)
    enriched = _enrich_contract_out(amendment)
    dispatch_global_event({
        "event": "contract_inserted",
        "table": "contracts",
        "type": "INSERT",
        "data": enriched.model_dump(mode="json"),
        "contract_id": str(amendment.id),
    })
    return enriched
