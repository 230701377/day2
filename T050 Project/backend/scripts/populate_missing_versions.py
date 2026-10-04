import os
import io
import sys
import hashlib
from datetime import datetime, timezone

sys.path.insert(0, ".")

from app.db.session import SessionLocal
from app.models.models import Contract, ContractVersion, Clause, RiskFinding, Obligation, User
from app.services.storage import get_storage, sha256_bytes
from app.services.ai.clauses import extract_clauses, classify_clauses_batch
from app.services.ai.risk import detect_risks, overall_risk_score
from app.services.obligations import extract_obligations_from_clauses

def generate_contract_text(c: Contract) -> str:
    counterparty = c.counterparty or "Enterprise Partners Inc."
    title = c.title or "Commercial Services Agreement"
    amount = f"${c.value_amount:,.2f}" if c.value_amount else "$50,000.00"
    
    return f"""{title.upper()}

This Agreement is entered into by and between Enterprise Corporation ("Company") and {counterparty} ("Counterparty").

1. SCOPE AND SERVICES
Counterparty shall perform professional services and deliverables as set forth in Exhibit A and relevant Statements of Work. All services shall be performed in a professional, workmanlike manner in accordance with high commercial industry standards.

2. COMPENSATION AND PAYMENT TERMS
Company shall pay Counterparty the total agreed contract value of {amount} USD. All invoices shall be payable Net 30 days from the invoice approval date. Late payments shall accrue interest at 1.0% per month or the legal maximum.

3. TERM AND TERMINATION
The initial term of this Agreement shall be twelve (12) months from the Effective Date. Either party may terminate this Agreement without cause upon sixty (60) days prior written notice, or immediately for material breach following a thirty (30) day cure period.

4. CONFIDENTIALITY AND NON-DISCLOSURE
Each party agrees to hold in confidence and not disclose proprietary or confidential technical, financial, or business information received from the other party without prior written authorization.

5. INTELLECTUAL PROPERTY AND WORK PRODUCT
All work product, custom software code, deliverables, and reports created under this Agreement shall belong solely and exclusively to Company upon receipt of payment.

6. INDEMNIFICATION AND WARRANTIES
Counterparty warrants that all services and deliverables provided do not infringe any patent, copyright, trademark, trade secret, or other intellectual property right of any third party. Counterparty agrees to defend, indemnify, and hold harmless Company from any third-party claims arising from a breach of this warranty.

7. LIMITATION OF LIABILITY
Except for confidentiality obligations or gross negligence, neither party's total aggregate liability arising out of or related to this Agreement shall exceed the fees paid or payable in the twelve (12) months preceding the incident.

8. GOVERNING LAW AND JURISDICTION
This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, United States, without giving effect to conflicts of law provisions.

IN WITNESS WHEREOF, the authorized representatives of the parties have executed this Agreement.
"""

def main():
    db = SessionLocal()
    storage = get_storage()
    admin = db.query(User).filter(User.role == "admin").first()
    admin_id = admin.id if admin else None

    contracts = db.query(Contract).all()
    count_updated = 0

    for c in contracts:
        v_count = db.query(ContractVersion).filter(ContractVersion.contract_id == c.id).count()
        if v_count > 0:
            continue

        print(f"Adding initial version for: {c.contract_number} - {c.title}")
        text = generate_contract_text(c)
        data = text.encode("utf-8")
        sha = sha256_bytes(data)
        safe_title = "".join(ch for ch in c.title if ch.isalnum() or ch in " _-").strip().replace(" ", "_").lower()
        filename = f"{safe_title}_agreement.txt"
        storage_key = f"contracts/{c.id}/v1_{sha[:10]}_{filename}"
        storage.put(storage_key, data)

        version = ContractVersion(
            contract_id=c.id,
            version_number=1,
            version_label="initial",
            storage_key=storage_key,
            original_filename=filename,
            mime_type="text/plain",
            size_bytes=len(data),
            sha256_hash=sha,
            page_count=3,
            content_text=text,
            change_summary="Initial executed contract document",
            created_by=c.owner_id or admin_id,
        )
        db.add(version)
        db.flush()

        # Extract clauses & risks if contract has none
        if len(c.clauses) == 0:
            page_text = [(1, text)]
            raw_clauses = extract_clauses(page_text)
            classifications = classify_clauses_batch(raw_clauses)
            for idx, (raw, (cat, conf)) in enumerate(zip(raw_clauses, classifications)):
                clause = Clause(
                    contract_id=c.id,
                    version_id=version.id,
                    clause_number=str(idx + 1),
                    heading=raw.get("title") or f"Clause {idx+1}",
                    body=raw["body"],
                    category=cat,
                    confidence=conf,
                    page_number=raw.get("page", 1),
                    risk_level="low",
                )
                db.add(clause)
            db.flush()

            # Detect risks
            detected_risks = detect_risks(raw_clauses)
            for r in detected_risks:
                risk = RiskFinding(
                    contract_id=c.id,
                    version_id=version.id,
                    finding_type=getattr(r, "finding_type", "risk_flag"),
                    severity=getattr(r, "severity", "medium"),
                    title=getattr(r, "title", "Risk Flag"),
                    description=getattr(r, "description", ""),
                    recommendation=getattr(r, "recommendation", ""),
                )
                db.add(risk)

            # Obligations
            all_clauses = db.query(Clause).filter(Clause.contract_id == c.id).all()
            clause_dicts = [{"clause_type": cl.category, "body": cl.body, "title": cl.heading} for cl in all_clauses]
            extracted_obs = extract_obligations_from_clauses(clause_dicts)
            for o in extracted_obs:
                ob = Obligation(
                    contract_id=c.id,
                    title=o.get("title", "Obligation"),
                    description=o.get("description", ""),
                    responsible_role=o.get("responsible_role", "legal"),
                    priority=o.get("priority", "medium"),
                    status="open",
                )
                db.add(ob)

        count_updated += 1

    db.commit()
    print(f"Successfully populated versions and analysis for {count_updated} contracts!")

if __name__ == "__main__":
    main()
