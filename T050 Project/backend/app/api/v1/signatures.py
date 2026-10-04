"""
API Router for Digital Signatures & Certificate Verification.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.models import User, Contract, ContractVersion
from app.services.signature_service import signature_service
from app.services.audit.chain import append as audit_append

router = APIRouter(prefix="/signatures", tags=["signatures"])


@router.post("/sign/{contract_id}/{version_id}")
def sign_contract_version(contract_id: str, version_id: str,
                           db: Session = Depends(get_db),
                           actor: User = Depends(get_current_user)):
    """
    Cryptographically signs a contract version with SHA-256 fingerprinting.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    version = db.query(ContractVersion).filter(
        ContractVersion.id == version_id,
        ContractVersion.contract_id == contract_id
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Contract version not found")

    cert = signature_service.sign_document(
        contract_id=contract_id,
        version_id=version_id,
        signer_email=actor.email,
        signer_name=actor.full_name or actor.email,
        content_text=version.content_text or ""
    )

    audit_append(db, actor=actor, action="contract.signed", resource_type="contract_version",
                 resource_id=str(version_id), payload=cert)
    db.commit()

    return cert


@router.post("/verify/{contract_id}/{version_id}")
def verify_contract_signature(contract_id: str, version_id: str, payload: dict,
                               db: Session = Depends(get_db),
                               actor: User = Depends(get_current_user)):
    """
    Verifies cryptographic signature integrity against document contents.
    """
    version = db.query(ContractVersion).filter(
        ContractVersion.id == version_id,
        ContractVersion.contract_id == contract_id
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Contract version not found")

    is_valid = signature_service.verify_signature(
        content_text=version.content_text or "",
        contract_id=contract_id,
        version_id=version_id,
        signature_hash=payload.get("signature_hash", ""),
        signer_email=payload.get("signer_email", ""),
        signed_at=payload.get("signed_at", "")
    )

    return {
        "contract_id": contract_id,
        "version_id": version_id,
        "verified": is_valid,
        "status": "VALID - Document Tamper-Free" if is_valid else "INVALID - Hash Mismatch Detected"
    }


@router.get("/{contract_id}/certificate")
def download_audit_certificate(contract_id: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    """
    Renders official Cryptographic Digital Signature Certificate HTML for print/download.
    """
    from fastapi.responses import HTMLResponse
    from app.services.pdf_certificate import generate_certificate_html
    from app.models.models import AuditLog

    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    version = db.query(ContractVersion).filter(ContractVersion.contract_id == contract_id).order_by(ContractVersion.version_number.desc()).first()
    raw_text = version.content_text if version else ""
    sha_fingerprint = version.sha256_hash if version else "SHA256-PENDING"

    # Fetch audit events
    audit_rows = db.query(AuditLog).filter(AuditLog.resource_id == str(contract_id)).order_by(AuditLog.timestamp.desc()).all()
    audit_events = [{
        "timestamp": str(a.timestamp),
        "action": a.action,
        "actor_email": str(a.actor_id)
    } for a in audit_rows]

    cert = signature_service.sign_document(
        contract_id=str(contract.id),
        version_id=str(version.id) if version else "v1",
        signer_email=actor.email,
        signer_name=actor.full_name or actor.email,
        content_text=raw_text
    )

    html_content = generate_certificate_html(
        contract_title=contract.title,
        contract_number=contract.contract_number,
        contract_id=str(contract.id),
        signer_name=actor.full_name or actor.email,
        signer_email=actor.email,
        signature_hash=cert["signature_hash"],
        signed_at=cert["signed_at"],
        sha256_fingerprint=sha_fingerprint,
        audit_events=audit_events
    )

    return HTMLResponse(content=html_content)

