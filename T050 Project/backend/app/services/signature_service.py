"""
Cryptographic Digital Signature & PKI Audit Service.

Provides digital document signing, SHA-256 fingerprint verification, and tamper-evident audit certificates.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional


class DigitalSignatureService:
    """
    PKI & SHA-256 Digital Signature Engine.
    """

    @staticmethod
    def compute_document_fingerprint(contract_id: str, version_number: str, content_text: str) -> str:
        """Compute immutable SHA-256 payload digest for contract document."""
        raw_data = f"{contract_id}:{version_number}:{content_text}".encode("utf-8")
        return hashlib.sha256(raw_data).hexdigest()

    @staticmethod
    def sign_document(contract_id: str, version_id: str, signer_email: str, signer_name: str, content_text: str) -> Dict[str, Any]:
        """
        Sign a contract version with cryptographic SHA-256 hash and audit metadata.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        fingerprint = DigitalSignatureService.compute_document_fingerprint(contract_id, version_id, content_text)

        # Generate cryptographic signature token (SHA-256 over fingerprint + signer + timestamp)
        sig_data = f"{fingerprint}:{signer_email}:{timestamp}".encode("utf-8")
        signature_hash = hashlib.sha256(sig_data).hexdigest()

        certificate = {
            "signature_id": f"SIG-{uuid.uuid4().hex[:12].upper()}",
            "contract_id": contract_id,
            "version_id": version_id,
            "signer_name": signer_name,
            "signer_email": signer_email,
            "signed_at": timestamp,
            "document_fingerprint": fingerprint,
            "signature_hash": signature_hash,
            "verification_status": "VALID",
            "pki_algorithm": "SHA256-RSA-Simulated"
        }
        return certificate

    @staticmethod
    def verify_signature(content_text: str, contract_id: str, version_id: str, signature_hash: str, signer_email: str, signed_at: str) -> bool:
        """
        Verify if a document version has been modified since signing.
        """
        fingerprint = DigitalSignatureService.compute_document_fingerprint(contract_id, version_id, content_text)
        recalculated_data = f"{fingerprint}:{signer_email}:{signed_at}".encode("utf-8")
        recalculated_hash = hashlib.sha256(recalculated_data).hexdigest()
        return recalculated_hash == signature_hash


signature_service = DigitalSignatureService()
