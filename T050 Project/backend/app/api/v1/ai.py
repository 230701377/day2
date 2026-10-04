from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.api.deps import get_current_user, get_current_user_optional
from app.models.models import (
    User, Contract, ContractVersion, Clause, RiskFinding, ContractMetadata,
    ContractTemplate, Obligation,
)
from app.schemas.schemas import (
    AnalysisOut, ClauseOut, RiskOut, VersionDiffOut
)
from app.services.parser import parse_document
from app.services.ai.clauses import extract_clauses, classify_clauses_batch
from app.services.ai.embeddings import encode, fit_corpus
from app.services.ai.risk import detect_risks, overall_risk_score
from app.services.ai.llm import summarize_heuristic, extract_metadata_heuristic
from app.services.ai.compare import compare_versions
from app.services.obligations import extract_obligations_from_clauses
from app.services.storage import get_storage, sha256_bytes
from app.services.audit.chain import append as audit_append
from app.services.chunker_service import chunker_service
from app.services.classifier_service import classifier_service
from app.services.duplicate_service import duplicate_service

router = APIRouter(prefix="/ai", tags=["ai"])


def _user_can_view(user: User, contract: Contract) -> bool:
    if user.role == "admin":
        return True
    if user.role == "requester":
        return contract.owner_id == user.id
    return user.role in {"legal", "finance", "manager", "compliance", "executive"}


def process_contract_background(contract_id: str, version_id: str):
    """
    Asynchronous background processing worker for contract documents.
    Executes Document Extraction, AI Classification, Metadata & Party Extraction,
    Clause Embeddings, Risk Analysis, Obligations, and Approval Generation.
    Guarantees resilient partial success processing without failing entire contract.
    """
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        version = db.query(ContractVersion).filter(ContractVersion.id == version_id).first()
        if not contract or not version:
            return

        # Step 1: Document Text Extraction (25%)
        from app.services.status_service import record_status_change
        old_proc_status = contract.processing_status
        contract.processing_status = "PROCESSING"
        contract.processing_step = "Document Extraction"
        contract.processing_progress = 25
        contract.processing_error = None
        record_status_change(db, str(contract.id), old_proc_status, "PROCESSING", reason="AI pipeline started")
        db.commit()

        storage = get_storage()
        text = version.content_text or ""
        page_text = []
        if not text and version.storage_key and storage.exists(version.storage_key):
            data = storage.get(version.storage_key)
            text, _, page_text, _ = parse_document(version.original_filename or "file", data)
            version.content_text = text
            db.commit()
        if not page_text and text:
            page_text = [(1, text)]

        # Step 2: Comprehensive Metadata & Party Extraction (45%)
        contract.processing_step = "Metadata & Party Extraction"
        contract.processing_progress = 45
        db.commit()

        try:
            from app.services.ai.metadata_extractor import extract_contract_metadata_complete
            meta = extract_contract_metadata_complete(text, filename=version.original_filename or "")

            if meta.get("counterparty"):
                contract.counterparty = meta["counterparty"]
            if meta.get("value_amount") is not None:
                contract.value_amount = meta["value_amount"]
            if meta.get("value_currency"):
                contract.value_currency = meta["value_currency"]
            if meta.get("effective_date"):
                contract.effective_date = meta["effective_date"]
            if meta.get("expiration_date"):
                contract.expiration_date = meta["expiration_date"]
            if meta.get("auto_renew") is not None:
                contract.auto_renew = meta["auto_renew"]
            if meta.get("renewal_notice_days") is not None:
                contract.renewal_notice_days = meta["renewal_notice_days"]
            if meta.get("contract_type"):
                contract.contract_type = meta["contract_type"]
            db.commit()
        except Exception as meta_err:
            db.rollback()

        # Step 3: Clause Extraction & Vector Embeddings (65%)
        contract.processing_step = "Clause Extraction & Vector Embeddings"
        contract.processing_progress = 65
        db.commit()

        clause_records = []
        try:
            raw_clauses = extract_clauses(page_text)
            classifications = classify_clauses_batch(raw_clauses)
            db.query(Clause).filter(Clause.version_id == version.id).delete()

            clause_bodies = [raw["body"] for raw in raw_clauses]
            all_embs = encode(clause_bodies) if clause_bodies else []

            for idx, (raw, (cat, conf)) in enumerate(zip(raw_clauses, classifications)):
                emb = all_embs[idx] if idx < len(all_embs) else None
                c = Clause(
                    contract_id=contract.id,
                    version_id=version.id,
                    clause_number=raw.get("clause_number"),
                    heading=raw.get("heading"),
                    body=raw["body"],
                    category=cat,
                    confidence=float(conf),
                    page_number=raw.get("page_number"),
                    start_offset=raw.get("start_offset"),
                    end_offset=raw.get("end_offset"),
                )
                if emb is not None:
                    c.embedding = emb.tolist()
                db.add(c)
                clause_records.append(c)
            db.flush()

            if clause_records:
                embs = [c.embedding for c in clause_records if c.embedding is not None]
                if embs:
                    import numpy as np
                    mean = np.mean(np.array(embs, dtype=np.float32), axis=0)
                    norm = np.linalg.norm(mean)
                    if norm > 0:
                        mean = mean / norm
                    version.embedding = mean.astype(np.float32).tolist()
            db.commit()
        except Exception as clause_err:
            db.rollback()

        # Step 4: Risk Analysis (85%)
        contract.processing_step = "Risk Analysis"
        contract.processing_progress = 85
        db.commit()

        try:
            clause_dicts = [
                {"clause_number": c.clause_number, "heading": c.heading, "body": c.body,
                 "page_number": c.page_number, "risk_level": c.risk_level}
                for c in clause_records
            ]
            hits = detect_risks(clause_dicts)
            db.query(RiskFinding).filter(RiskFinding.version_id == version.id).delete()
            for h in hits:
                rec = RiskFinding(
                    contract_id=contract.id,
                    version_id=version.id,
                    clause_id=None,
                    finding_type=h.finding_type,
                    severity=h.severity,
                    score_rule=round(h.score_rule, 3),
                    score_nlp=round(h.score_nlp, 3),
                    score_llm=round(h.score_llm, 3),
                    score_total=round(h.score_total, 3),
                    title=h.title,
                    description=h.description,
                    evidence=h.evidence,
                    recommendation=h.recommendation,
                    source_excerpt=h.source_excerpt,
                    source_page=h.source_page,
                )
                for c in clause_records:
                    if (c.page_number == h.source_page) and (
                        h.source_excerpt and c.body[:120] and h.source_excerpt[:80] in c.body
                    ):
                        rec.clause_id = c.id
                        break
                db.add(rec)

            risk_score, risk_level = overall_risk_score(hits)
            contract.risk_score = risk_score
            contract.risk_level = risk_level

            summary = summarize_heuristic(text, max_sentences=5)
            if not version.change_summary:
                version.change_summary = summary
            db.commit()
        except Exception as risk_err:
            db.rollback()

        # Step 5: Obligations & Approval Workflow (95%)
        contract.processing_step = "Approval Workflow & Obligations"
        contract.processing_progress = 95
        db.commit()

        try:
            if clause_records:
                obligations = extract_obligations_from_clauses(clause_records)
                db.query(Obligation).filter(Obligation.contract_id == contract.id).delete()
                for ob in obligations:
                    o = Obligation(
                        contract_id=contract.id,
                        title=ob["title"][:200],
                        description=ob["description"],
                        responsible_role="legal" if ob.get("category") in {"indemnification", "compliance"} else None,
                        priority=ob["priority"],
                        source_clause_id=ob.get("source_clause_id"),
                    )
                    db.add(o)

            from app.services.workflow_service import generate_approvals_for_contract
            generate_approvals_for_contract(db, contract)
            db.commit()
        except Exception as wf_err:
            db.rollback()

        # Step 6: Final Completion (100%)
        contract.processing_status = "COMPLETED"
        contract.processing_step = "Completed"
        contract.processing_progress = 100
        contract.processing_error = None
        record_status_change(db, str(contract.id), "PROCESSING", "COMPLETED", reason="AI pipeline completed successfully")
        db.commit()

    except Exception as exc:
        db.rollback()
        try:
            cnt = db.query(Contract).filter(Contract.id == contract_id).first()
            if cnt:
                cnt.processing_status = "FAILED"
                cnt.processing_step = "Failed"
                cnt.processing_error = str(exc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/analyze/{contract_id}/{version_id}", response_model=AnalysisOut)
def analyze_version(contract_id: str, version_id: str, db: Session = Depends(get_db),
                     actor: User = Depends(get_current_user)):
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if not _user_can_view(actor, contract):
        raise HTTPException(status_code=403, detail="Not authorized")
    version = db.query(ContractVersion).filter(
        ContractVersion.id == version_id,
        ContractVersion.contract_id == contract_id
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    process_contract_background(contract_id, version_id)
    db.refresh(contract)
    db.refresh(version)

    clauses = db.query(Clause).filter(Clause.version_id == version.id).all()
    risks = db.query(RiskFinding).filter(RiskFinding.version_id == version.id).all()

    return AnalysisOut(
        contract_id=str(contract.id),
        version_id=str(version.id),
        status=contract.processing_status,
        summary=version.change_summary,
        clauses=clauses,
        risks=risks,
        risk_score=contract.risk_score,
        risk_level=contract.risk_level,
    )


@router.get("/compare/{contract_id}", response_model=VersionDiffOut)
def compare_contract_versions(
    contract_id: str,
    from_version: int = Query(...),
    to_version: int = Query(...),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if not _user_can_view(actor, contract):
        raise HTTPException(status_code=403, detail="Not authorized")
    v1 = db.query(ContractVersion).filter(
        ContractVersion.contract_id == contract_id,
        ContractVersion.version_number == from_version
    ).first()
    v2 = db.query(ContractVersion).filter(
        ContractVersion.contract_id == contract_id,
        ContractVersion.version_number == to_version
    ).first()
    if not v1 or not v2:
        raise HTTPException(status_code=404, detail="One or both versions not found")

    c1 = db.query(Clause).filter(Clause.version_id == v1.id).all()
    c2 = db.query(Clause).filter(Clause.version_id == v2.id).all()
    d1 = [{"clause_number": c.clause_number, "heading": c.heading, "body": c.body,
           "page_number": c.page_number, "risk_level": c.risk_level} for c in c1]
    d2 = [{"clause_number": c.clause_number, "heading": c.heading, "body": c.body,
           "page_number": c.page_number, "risk_level": c.risk_level} for c in c2]
    diff = compare_versions(d1, d2)
    # risk delta from persisted findings
    from app.models.models import RiskFinding
    r1 = db.query(RiskFinding).filter(RiskFinding.version_id == v1.id).all()
    r2 = db.query(RiskFinding).filter(RiskFinding.version_id == v2.id).all()
    s1 = sum(f.score_total for f in r1)
    s2 = sum(f.score_total for f in r2)
    diff["risk_delta"] = round(s2 - s1, 2)
    return VersionDiffOut(**diff)


@router.get("/clauses/{contract_id}", response_model=List[ClauseOut])
def list_clauses(contract_id: str, version_id: Optional[str] = None,
                  db: Session = Depends(get_db),
                  actor: User = Depends(get_current_user)):
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract or not _user_can_view(actor, contract):
        raise HTTPException(status_code=403, detail="Not authorized")
    q = db.query(Clause).filter(Clause.contract_id == contract_id)
    if version_id:
        q = q.filter(Clause.version_id == version_id)
    return q.order_by(Clause.page_number.asc(), Clause.id.asc()).all()


@router.get("/risks/{contract_id}", response_model=List[RiskOut])
def list_risks(contract_id: str, version_id: Optional[str] = None,
                db: Session = Depends(get_db),
                actor: User = Depends(get_current_user)):
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract or not _user_can_view(actor, contract):
        raise HTTPException(status_code=403, detail="Not authorized")
    q = db.query(RiskFinding).filter(RiskFinding.contract_id == contract_id)
    if version_id:
        q = q.filter(RiskFinding.version_id == version_id)
    return q.order_by(RiskFinding.score_total.desc()).all()


@router.post("/classify")
def classify_contract_endpoint(payload: dict, actor: User = Depends(get_current_user)):
    """
    Azure AI Contract Classifier Endpoint.
    Classifies legal contract text or metadata into canonical categories.
    """
    text = payload.get("text", "")
    parties = payload.get("parties", [])
    if not text and not parties:
        raise HTTPException(status_code=400, detail="Text or parties payload required for classification")
    result = classifier_service.classify_contract(text=text, parties=parties)
    return result


@router.post("/semantic-chunks")
def semantic_chunks_endpoint(payload: dict, actor: User = Depends(get_current_user)):
    """
    Semantic Chunker Service Endpoint.
    Generates contextual clause/section chunks with pgvector metadata.
    """
    text = payload.get("text", "")
    contract_id = payload.get("contract_id", "temp_doc")
    if not text:
        raise HTTPException(status_code=400, detail="Text payload required for semantic chunking")
    chunks = chunker_service.chunk_contract(contract_id=contract_id, raw_text=text)
    return {
        "contract_id": contract_id,
        "total_chunks": len(chunks),
        "chunks": chunks
    }


@router.post("/detect-duplicates")
def detect_duplicates_endpoint(payload: dict, db: Session = Depends(get_db), actor: Optional[User] = Depends(get_current_user_optional)):
    """
    AI Duplicate Contract Detection Endpoint (Text Payload).
    Compares uploaded contract text against repository documents.
    """
    text = payload.get("text", "")
    contract_id = payload.get("contract_id", "")
    threshold = float(payload.get("threshold", 0.45))
    result = duplicate_service.detect_duplicates_in_db(db=db, new_text=text, current_contract_id=contract_id, threshold=threshold)
    return result


@router.post("/detect-duplicates-file")
async def detect_duplicates_file_endpoint(
    file: UploadFile = File(...),
    threshold: float = Form(0.85),
    db: Session = Depends(get_db),
    actor: Optional[User] = Depends(get_current_user_optional)
):
    """
    AI Duplicate Contract Detection Endpoint (File Payload: PDF, DOCX, TXT).
    Parses file bytes, extracts text, computes SHA-256, and checks against database.
    """
    data = await file.read()
    if not data:
        return {"has_duplicate": False, "matches": [], "message": "File payload is empty"}

    from app.services.parser import parse_document
    from app.services.storage import sha256_bytes
    sha = sha256_bytes(data)
    text, pages, page_text, mime = parse_document(file.filename or "file", data)

    result = duplicate_service.detect_duplicates_in_db(
        db=db,
        new_text=text,
        new_filename=file.filename or "",
        sha256_hash=sha,
        threshold=threshold
    )
    return result


