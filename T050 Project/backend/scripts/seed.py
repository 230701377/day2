"""
Seed script - creates realistic users across all roles, contract templates,
approval workflows, and a portfolio of demo contracts that exercise every
part of the system (different types, values, risk profiles, statuses,
amendments, renewals). All seeded contracts get analyzed so the UI has
clauses, risks, obligations and embeddings populated out-of-the-box.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.core.security import hash_password
from app.core.config import settings
from app.models.models import (
    User, Contract, ContractVersion, Clause, RiskFinding,
    ContractMetadata, ApprovalWorkflow, Approval, Obligation,
    ContractTemplate, AuditLog, ContractStatus, ApprovalDecision, RiskLevel
)
from app.services.workflow.engine import (
    DEFAULT_WORKFLOW, HIGH_VALUE_WORKFLOW, LOW_RISK_WORKFLOW,
)
from app.services.storage import get_storage, sha256_bytes
from app.services.parser import parse_document
from app.services.ai.clauses import extract_clauses, classify_clauses_batch
from app.services.ai.embeddings import encode
from app.services.ai.risk import detect_risks, overall_risk_score
from app.services.ai.llm import extract_metadata_heuristic, summarize_heuristic
from app.services.obligations import extract_obligations_from_clauses
from app.services.audit.chain import append as audit_append


# Realistic, non-generic contract bodies used to seed the repository.
SAMPLE_CONTRACTS = {
    "nda": {
        "title": "Mutual Non-Disclosure Agreement - Acme Robotics & Nimbus Analytics",
        "counterparty": "Nimbus Analytics Pvt. Ltd.",
        "department": "Business Development",
        "value_amount": 0.0,
        "tags": ["nda", "mutual"],
        "description": "Mutual NDA to facilitate exploratory discussions around a potential strategic partnership.",
        "filename": "nda_acme_nimbus.txt",
        "body": """MUTUAL NON-DISCLOSURE AGREEMENT

This Mutual Non-Disclosure Agreement ("Agreement") is entered into as of January 15, 2025 (the "Effective Date") by and between Acme Robotics, Inc., a Delaware corporation having its principal place of business at 500 Market Street, San Francisco, CA ("Acme"), and Nimbus Analytics, Inc., a New York corporation having its principal place of business at 350 Fifth Avenue, New York, NY ("Nimbus"). Acme and Nimbus may be referred to individually as a "Party" and collectively as the "Parties."

1. Definitions.
"Confidential Information" means any non-public information disclosed by one Party (the "Discloser") to the other Party (the "Recipient"), whether orally or in writing, that is designated as confidential or that reasonably should be understood to be confidential given the nature of the information and the circumstances of disclosure.

2. Obligations of Recipient.
The Recipient shall (a) hold the Confidential Information in strict confidence, (b) use the Confidential Information solely for the purpose of evaluating a potential business relationship between the Parties, and (c) protect the Confidential Information using the same degree of care it uses to protect its own confidential information of like importance, but in no event less than reasonable care.

3. Exclusions.
Confidential Information does not include information that (a) is or becomes publicly known through no fault of the Recipient, (b) was already known to the Recipient prior to disclosure, (c) is rightfully received by the Recipient from a third party without restriction, or (d) is independently developed by the Recipient without use of the Confidential Information.

4. Term.
This Agreement shall commence on the Effective Date and continue for a period of two (2) years thereafter, unless earlier terminated. Either party may terminate this Agreement upon thirty days written notice.

5. No License.
Nothing in this Agreement shall be construed as granting either Party any rights, by license or otherwise, in any Confidential Information of the other Party except as expressly set forth herein.

6. Governing Law.
This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, without regard to its conflict of laws principles. The parties consent to the exclusive jurisdiction of the courts located in New Castle County, Delaware.

7. Entire Agreement.
This Agreement constitutes the entire agreement between the Parties with respect to the subject matter hereof and supersedes all prior understandings.

IN WITNESS WHEREOF, the Parties have executed this Agreement as of the Effective Date.
""",
    },
    "msa": {
        "title": "Master Services Agreement - Globex Cloud Platform",
        "counterparty": "Globex Systems Pvt. Ltd.",
        "department": "Engineering",
        "value_amount": 8500000.0,
        "tags": ["msa", "cloud", "saas"],
        "description": "Three-year MSA governing cloud infrastructure services with auto-renewal.",
        "filename": "msa_globex.txt",
        "body": """MASTER SERVICES AGREEMENT

This Master Services Agreement ("Agreement") is entered into as of March 1, 2025 between Acme Robotics, Inc. ("Customer") and Globex Systems LLC ("Provider").

1. Services.
Provider shall provide cloud infrastructure and managed services as described in one or more Statements of Work ("SOWs") executed under this Agreement.

2. Term.
The initial term of this Agreement shall be three (3) years commencing on the Effective Date. This Agreement will automatically renew for additional one-year terms unless either party provides written notice of non-renewal at least sixty days prior to the end of the then-current term.

3. Fees and Payment.
Customer shall pay Provider the fees set forth in each SOW. All undisputed invoices are payable Net 30 from the invoice date. Late payments shall accrue interest at the lesser of 1.5% per month or the maximum rate permitted by law.

4. Service Levels.
Provider shall maintain a monthly uptime of 99.9% for the hosted service, measured on a rolling 30-day basis. Service level credits shall be issued for failure to meet the agreed service levels according to the schedule attached as Exhibit B.

5. Confidentiality.
Each party agrees to maintain the confidentiality of all Confidential Information disclosed by the other party and to protect such information using the same degree of care it uses for its own confidential information.

6. Intellectual Property.
Provider retains all right, title and interest in and to its pre-existing intellectual property and any general improvements thereto. Customer retains all right, title and interest in and to its data and content.

7. Indemnification.
Provider shall indemnify, defend and hold harmless Customer from any third-party claims arising from Provider's negligence or willful misconduct, including any claims that the Services infringe any third-party intellectual property rights.

8. Limitation of Liability.
In no event shall either party's liability exceed the fees paid by Customer to Provider in the twelve months preceding the event giving rise to the claim. Neither party shall be liable for any indirect, incidental, special or consequential damages.

9. Data Protection.
Processor shall implement appropriate technical and organizational measures to protect Personal Data in accordance with applicable data protection laws including GDPR and CCPA. Processor shall notify Customer of any personal data breach without undue delay and in any event within 72 hours.

10. Termination.
Either party may terminate this Agreement for material breach upon thirty days written notice if the breach is not cured during such period. The Company may terminate this Agreement immediately upon written notice for cause.

11. Force Majeure.
Neither party shall be liable for any failure or delay due to causes beyond its reasonable control, including acts of God, war, terrorism, pandemic and governmental action.

12. Audit Rights.
Customer may audit Provider's books and records relating to this Agreement once per year, with at least 30 days prior written notice, during normal business hours.

13. Assignment.
Neither party may assign this Agreement without the prior written consent of the other party, except to an affiliate or in connection with a merger, acquisition or sale of all or substantially all of its assets.

14. Governing Law.
This Agreement shall be governed by the laws of the State of California, without regard to its conflict of laws principles. The parties consent to the exclusive jurisdiction of the courts located in San Francisco County, California.

15. Entire Agreement.
This Agreement constitutes the entire agreement between the parties and supersedes all prior understandings. No amendment to this Agreement is effective unless made in writing and signed by both parties.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the Effective Date.
""",
    },
    "vendor": {
        "title": "Vendor Agreement - Helios Marketing Services",
        "counterparty": "Helios Marketing Pvt. Ltd.",
        "department": "Marketing",
        "value_amount": 1850000.0,
        "tags": ["vendor", "marketing"],
        "description": "12-month marketing services vendor agreement.",
        "filename": "vendor_helios.txt",
        "body": """VENDOR SERVICES AGREEMENT

This Vendor Services Agreement is entered into as of February 10, 2025 between Acme Robotics, Inc. ("Customer") and Helios Marketing Group ("Vendor").

1. Services.
Vendor shall provide digital marketing services including campaign management, content creation and analytics reporting as further described in Exhibit A.

2. Term.
The initial term is twelve months. This Agreement may be renewed by mutual written agreement of the parties.

3. Compensation.
Customer shall pay Vendor ₹18,50,000 (eighteen lakh fifty thousand rupees) for the initial term, payable in twelve equal monthly installments net 30 days from invoice date.

4. Deliverables.
Vendor shall deliver monthly performance reports, campaign creative assets, and quarterly strategy reviews.

5. Warranty.
Vendor warrants that the Services will be performed in a professional and workmanlike manner consistent with industry standards.

6. Termination.
Either party may terminate this Agreement for material breach upon thirty days written notice.

7. Limitation of Liability.
Vendor's liability under this Agreement shall be limited to the fees paid in the three months preceding the claim.

8. Governing Law.
This Agreement shall be governed by the laws of the State of New York.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the Effective Date.
""",
    },
    "lease": {
        "title": "Office Lease - 100 Innovation Drive, Building B",
        "counterparty": "Pacific Real Estate Holdings",
        "department": "Operations",
        "value_amount": 9600000.0,
        "tags": ["lease", "office"],
        "description": "Three-year commercial office lease with renewal option.",
        "filename": "lease_innovation.txt",
        "body": """COMMERCIAL OFFICE LEASE

This Lease is entered into as of May 1, 2024 between Pacific Real Estate Holdings ("Landlord") and Acme Robotics, Inc. ("Tenant").

1. Premises.
Landlord leases to Tenant approximately 8,500 rentable square feet on the third floor of 100 Innovation Drive, Building B ("Premises").

2. Term.
The initial term is three (3) years commencing on the Commencement Date. Tenant has one option to renew for an additional three-year term by providing written notice at least ninety days prior to expiration.

3. Rent.
Tenant shall pay base rent of ₹96,00,000 (ninety-six lakh rupees) per year, payable in equal monthly installments on the first day of each month. Rent shall increase by 5% annually.

4. Use.
The Premises shall be used solely for general office and research and development activities.

5. Insurance.
Tenant shall maintain commercial general liability insurance with limits not less than ₹2,00,00,000 (two crore rupees) per occurrence.

6. Termination.
Tenant may terminate this Agreement upon 90 days written notice subject to an early termination fee equal to two months rent.

7. Governing Law.
This Lease shall be governed by the laws of the State of California.

IN WITNESS WHEREOF, the parties have executed this Lease as of the Commencement Date.
""",
    },
    "employment": {
        "title": "Executive Employment Agreement - CTO",
        "counterparty": "Internal - Executive",
        "department": "Human Resources",
        "value_amount": 8500000.0,
        "tags": ["employment", "executive"],
        "description": "Executive employment agreement for incoming Chief Technology Officer.",
        "filename": "employment_cto.txt",
        "body": """EXECUTIVE EMPLOYMENT AGREEMENT

This Employment Agreement is entered into as of April 1, 2025 between Acme Robotics, Inc. ("Company") and the Executive named on the signature page ("Executive").

1. Position.
Executive shall serve as Chief Technology Officer and report to the Chief Executive Officer.

2. Compensation.
The Company shall pay Executive an annual base salary of ₹85,00,000 (eighty-five lakh rupees), payable in accordance with the Company's standard payroll practices.

3. Equity.
Executive shall be granted 80,000 Employee Stock Options vesting over four years with a one-year cliff, exercisable at the fair market value on the date of grant.

4. Benefits.
Executive shall be eligible to participate in the Company's standard benefits programs including health, dental, vision and 401(k).

5. Non-Compete.
During the term of employment and for twelve months thereafter, Executive shall not engage in any business that competes with the Company in the United States.

6. Confidentiality.
Executive shall maintain the confidentiality of all Confidential Information of the Company both during and after employment.

7. Termination.
Either party may terminate this Agreement for material breach upon 30 days written notice. The Company may terminate this Agreement immediately for cause.

8. Governing Law.
This Agreement shall be governed by the laws of the State of Delaware.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the Effective Date.
""",
    },
    "risky": {
        "title": "Vendor Agreement - Quantum Logistics (HIGH RISK)",
        "counterparty": "Quantum Logistics International",
        "department": "Supply Chain",
        "value_amount": 12500000.0,
        "tags": ["vendor", "high-risk", "exclusive"],
        "description": "Aggressive vendor agreement - intentionally contains several risky clauses to demonstrate risk detection.",
        "filename": "vendor_quantum_risky.txt",
        "body": """VENDOR SERVICES AGREEMENT - QUANTUM LOGISTICS

This Vendor Services Agreement is entered into as of June 1, 2025 between Acme Robotics, Inc. ("Customer") and Quantum Logistics International ("Vendor").

1. Services.
Vendor shall provide freight, warehousing and last-mile delivery services exclusively for Customer across North America, Europe, and Asia for the entire term.

2. Term and Exclusivity.
The initial term is twenty-four months and shall automatically renew for additional twelve-month terms unless terminated in writing. Vendor is appointed as the exclusive provider of logistics services for Customer; Vendor shall provide such services without additional compensation.

3. Fees and Payment.
Customer shall pay the fees set forth in Exhibit A. All invoices are due within five days of receipt. Late payments shall accrue interest at 2% per month.

4. Liquidated Damages.
In the event of termination by Customer, Customer shall pay liquidated damages in excess of ₹5,00,00,000 (five crore rupees).

5. Limitation of Liability.
In no event shall Vendor's liability exceed the fees paid in the one month preceding the claim. Customer's liability for unpaid invoices shall be unlimited.

6. IP and Audit.
Vendor may assign all intellectual property created in the course of the engagement to Customer as a present assignment. Customer may audit Vendor's books and records at any time without prior notice.

7. Termination.
Vendor may terminate this Agreement at any time and at its sole discretion upon written notice. The Company may terminate this Agreement immediately for cause.

8. Indemnification.
Vendor shall indemnify, defend and hold harmless Customer from any and all losses, damages, claims and liabilities arising from or related to the Services.

9. Data Protection.
There is no reference to GDPR or CCPA compliance in this Agreement; the parties agree to address data protection as needed.

10. Governing Law.
This Agreement shall be governed by the laws of the State of Texas. Force majeure events include any cause beyond Vendor's reasonable control including those determined by Vendor in its sole discretion.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the Effective Date.
""",
    },
}


USERS = [
    {"email": "admin@acme.io", "full_name": "Alex Admin", "role": "admin", "department": "IT"},
    {"email": "exec@acme.io", "full_name": "Erin Executive", "role": "executive", "department": "Executive"},
    {"email": "legal@acme.io", "full_name": "Laura Legal", "role": "legal", "department": "Legal"},
    {"email": "finance@acme.io", "full_name": "Frank Finance", "role": "finance", "department": "Finance"},
    {"email": "compliance@acme.io", "full_name": "Casey Compliance", "role": "compliance", "department": "Compliance"},
    {"email": "manager@acme.io", "full_name": "Morgan Manager", "role": "manager", "department": "Operations"},
    {"email": "requester@acme.io", "full_name": "Riley Requester", "role": "requester", "department": "Engineering"},
    {"email": "requester2@acme.io", "full_name": "Robin Requester", "role": "requester", "department": "Marketing"},
    {"email": "legal2@acme.io", "full_name": "Logan Legal", "role": "legal", "department": "Legal"},
    {"email": "manager2@acme.io", "full_name": "Max Manager", "role": "manager", "department": "Engineering"},
]


PASSWORD = "Demo1234!"


def _ensure_users(db):
    out = {}
    for u in USERS:
        existing = db.query(User).filter(User.email == u["email"]).first()
        if existing:
            out[u["email"]] = existing
            continue
        user = User(
            email=u["email"], full_name=u["full_name"], role=u["role"],
            department=u["department"], hashed_password=hash_password(PASSWORD),
        )
        db.add(user)
        db.flush()
        out[u["email"]] = user
    db.commit()
    return out


def _ensure_workflows(db):
    out = {}
    for cfg in [DEFAULT_WORKFLOW, HIGH_VALUE_WORKFLOW, LOW_RISK_WORKFLOW]:
        wf = db.query(ApprovalWorkflow).filter(ApprovalWorkflow.name == cfg["name"]).first()
        if not wf:
            wf = ApprovalWorkflow(**cfg)
            db.add(wf)
            db.flush()
        out[cfg["name"]] = wf
    db.commit()
    return out


def _ensure_templates(db):
    templates = {
        "Standard NDA": {
            "contract_type": "nda",
            "description": "Mutual non-disclosure agreement template.",
            "required_clauses": ["confidentiality", "term", "governing_law"],
            "recommended_clauses": ["entire_agreement", "notices"],
            "body": SAMPLE_CONTRACTS["nda"]["body"],
        },
        "Standard MSA": {
            "contract_type": "msa",
            "description": "Master services agreement template.",
            "required_clauses": ["term", "payment_terms", "limitation_of_liability", "confidentiality",
                                 "intellectual_property", "indemnification", "governing_law"],
            "recommended_clauses": ["data_protection", "service_levels", "audit_rights", "termination"],
            "body": SAMPLE_CONTRACTS["msa"]["body"],
        },
        "Vendor Services Agreement": {
            "contract_type": "vendor",
            "description": "Standard vendor services agreement template.",
            "required_clauses": ["payment_terms", "term", "limitation_of_liability", "warranty"],
            "recommended_clauses": ["termination", "insurance", "governing_law"],
            "body": SAMPLE_CONTRACTS["vendor"]["body"],
        },
    }
    out = {}
    for name, cfg in templates.items():
        t = db.query(ContractTemplate).filter(ContractTemplate.name == name).first()
        if not t:
            t = ContractTemplate(name=name, **cfg)
            db.add(t)
            db.flush()
        out[name] = t
    db.commit()
    return out


def _create_contract(db, users, owner, template, sample_key, status_value,
                      days_to_expiry=None):
    sample = SAMPLE_CONTRACTS[sample_key]
    contract = Contract(
        title=sample["title"],
        contract_number=f"CT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{sample_key.upper()[:3]}",
        contract_type=sample["counterparty"].lower() if False else (
            {"nda": "nda", "msa": "msa", "vendor": "vendor", "lease": "lease",
             "employment": "employment", "risky": "vendor"}[sample_key]),
        status=status_value,
        counterparty=sample["counterparty"],
        owner_id=owner.id,
        department=sample["department"],
        value_amount=sample["value_amount"],
        value_currency="INR",
        effective_date=datetime.now(timezone.utc) - timedelta(days=120),
        expiration_date=(
            datetime.now(timezone.utc) + timedelta(days=days_to_expiry)
            if days_to_expiry is not None else None
        ),
        auto_renew=(sample_key in ("msa",)),
        renewal_notice_days=60,
        description=sample["description"],
        tags=sample.get("tags", []),
        template_id=template.id if template else None,
    )
    db.add(contract)
    db.flush()

    # Store a version with parsed text + embeddings + clauses + risks + obligations
    body = sample["body"]
    data = body.encode("utf-8")
    storage = get_storage()
    sha = sha256_bytes(data)
    storage_key = f"contracts/{contract.id}/v1_{sha[:10]}_{sample['filename']}"
    storage.put(storage_key, data)

    text, page_count, page_text, mime = parse_document(sample["filename"], data)
    raw_clauses = extract_clauses(page_text)
    classifications = classify_clauses_batch(raw_clauses)

    version = ContractVersion(
        contract_id=contract.id,
        version_number=1,
        version_label="initial",
        storage_key=storage_key,
        original_filename=sample["filename"],
        mime_type="text/plain",
        size_bytes=len(data),
        sha256_hash=sha,
        page_count=page_count,
        content_text=text,
        created_by=owner.id,
    )
    db.add(version)
    db.flush()

    clause_records = []
    for raw, (cat, conf) in zip(raw_clauses, classifications):
        emb = encode([raw["body"]])[0]
        c = Clause(
            contract_id=contract.id, version_id=version.id,
            clause_number=raw.get("clause_number"),
            heading=raw.get("heading"),
            body=raw["body"],
            category=cat,
            confidence=float(conf),
            page_number=raw.get("page_number"),
            start_offset=raw.get("start_offset"),
            end_offset=raw.get("end_offset"),
        )
        c.embedding = emb.tolist()
        db.add(c)
        clause_records.append(c)
    db.flush()

    import numpy as np
    if clause_records:
        embs = [c.embedding for c in clause_records if c.embedding is not None]
        if embs:
            mean = np.mean(np.array(embs, dtype=np.float32), axis=0)
            norm = np.linalg.norm(mean)
            if norm > 0:
                mean /= norm
            version.embedding = mean.astype(np.float32).tolist()
            db.flush()

    md = extract_metadata_heuristic(text)
    cm = ContractMetadata(contract_id=contract.id, **md)
    db.add(cm)
    db.flush()

    clause_dicts = [
        {"clause_number": c.clause_number, "heading": c.heading, "body": c.body,
         "page_number": c.page_number, "risk_level": c.risk_level}
        for c in clause_records
    ]
    hits = detect_risks(clause_dicts)
    for h in hits:
        rf = RiskFinding(
            contract_id=contract.id, version_id=version.id,
            finding_type=h.finding_type, severity=h.severity,
            score_rule=h.score_rule, score_nlp=h.score_nlp, score_llm=h.score_llm,
            score_total=h.score_total, title=h.title, description=h.description,
            evidence=h.evidence, recommendation=h.recommendation,
            source_excerpt=h.source_excerpt, source_page=h.source_page,
        )
        for c in clause_records:
            if (c.page_number == h.source_page) and (
                h.source_excerpt and c.body[:120] and h.source_excerpt[:80] in c.body
            ):
                rf.clause_id = c.id
                break
        db.add(rf)
    db.flush()
    risk_score, risk_level = overall_risk_score(hits)
    contract.risk_score = risk_score
    contract.risk_level = risk_level

    obligations = extract_obligations_from_clauses(clause_records)
    for ob in obligations[:10]:
        o = Obligation(
            contract_id=contract.id,
            title=ob["title"][:200],
            description=ob["description"],
            responsible_role="legal" if ob.get("category") in {"indemnification", "compliance"} else None,
            priority=ob["priority"],
            source_clause_id=ob.get("source_clause_id"),
        )
        db.add(o)
    db.flush()

    version.change_summary = summarize_heuristic(text, max_sentences=4)
    db.flush()

    # audit
    audit_append(db, actor=owner, action="contract.seed_create",
                 resource_type="contract", resource_id=str(contract.id),
                 payload={"sample_key": sample_key, "risk_score": risk_score})
    db.commit()
    return contract


def _create_amendment(db, parent, users):
    sample = SAMPLE_CONTRACTS["msa"]
    amendment_body = sample["body"] + "\n\nAMENDMENT 1\nThe parties agree to extend the term by an additional twelve months and to increase the annual fees by 5%. All other terms remain unchanged.\n"
    owner = users["requester@acme.io"]
    amendment = Contract(
        title=f"Amendment 1 to {parent.title}",
        contract_number=f"CT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-AMD",
        contract_type=parent.contract_type,
        status=ContractStatus.DRAFT.value,
        counterparty=parent.counterparty,
        owner_id=owner.id,
        department=parent.department,
        value_amount=(parent.value_amount or 0) * 1.05,
        value_currency="USD",
        effective_date=parent.expiration_date or datetime.now(timezone.utc),
        expiration_date=(parent.expiration_date or datetime.now(timezone.utc)) + timedelta(days=365),
        auto_renew=parent.auto_renew,
        renewal_notice_days=parent.renewal_notice_days,
        description="Amendment 1 extending term and adjusting fees.",
        tags=parent.tags or [],
        parent_contract_id=parent.id,
        is_amendment=True,
    )
    db.add(amendment)
    db.flush()
    audit_append(db, actor=owner, action="contract.seed_amendment",
                 resource_type="contract", resource_id=str(amendment.id),
                 payload={"parent_contract_id": str(parent.id)})
    db.commit()
    return amendment


def _start_workflow_for(db, contract, users, leave_pending: bool = False):
    """Start an approval workflow and immediately advance all steps so the
    demo can show the full lifecycle (approved or active contracts).

    If leave_pending=True, the first step is left as 'pending' so the demo
    can show manual approval routing in the UI.
    """
    from app.services.workflow.engine import start_workflow, select_workflow_for
    wf = select_workflow_for(db, contract)
    if not wf:
        return
    approvals = start_workflow(db, contract, users["admin@acme.io"], wf)
    db.commit()
    if contract.status not in {"draft", "in_review"}:
        return
    if leave_pending:
        # Leave the first step pending so the demo can approve it manually.
        if approvals:
            approvals[0].comments = "Awaiting review."
        db.commit()
        return
    for ap in approvals:
        ap.decision = ApprovalDecision.APPROVED.value
        ap.comments = "Auto-approved during seed."
        ap.decided_at = datetime.now(timezone.utc)
    contract.status = ContractStatus.APPROVED.value
    if contract.effective_date and contract.effective_date < datetime.now(timezone.utc):
        contract.status = ContractStatus.ACTIVE.value
    db.commit()


def main():
    db = SessionLocal()
    try:
        print("Seeding users...")
        users = _ensure_users(db)
        print(f"  -> {len(users)} users")
        print("Seeding workflows...")
        workflows = _ensure_workflows(db)
        print(f"  -> {len(workflows)} workflows")
        print("Seeding templates...")
        templates = _ensure_templates(db)
        print(f"  -> {len(templates)} templates")

        print("Seeding contracts...")
        owner = users["requester@acme.io"]
        contract_specs = [
            ("nda", "Standard NDA", "active", 180),
            ("msa", "Standard MSA", "active", 800),
            ("vendor", "Vendor Services Agreement", "active", 120),
            ("lease", None, "active", 200),
            ("employment", None, "active", 600),
            ("risky", None, "in_review", 90),
        ]
        seeded = []
        for key, tpl_name, status_value, days_to_expiry in contract_specs:
            existing = db.query(Contract).filter(
                Contract.counterparty == SAMPLE_CONTRACTS[key]["counterparty"]
            ).first()
            if existing:
                seeded.append(existing)
                continue
            c = _create_contract(db, users, owner,
                                  templates.get(tpl_name) if tpl_name else None,
                                  key, status_value, days_to_expiry=days_to_expiry)
            seeded.append(c)
            print(f"  -> {c.title}")
        db.commit()

        # Create an amendment for the MSA so the demo can show diff
        msa = next((c for c in seeded if "Globex" in (c.counterparty or "")), None)
        if msa and not db.query(Contract).filter(Contract.parent_contract_id == msa.id).first():
            print("Seeding amendment...")
            _create_amendment(db, msa, users)

        # Run workflows on the risky + draft ones
        print("Starting approval workflows on in-review contracts...")
        for c in seeded:
            if c.status in {"draft", "in_review"} and not db.query(Approval).filter(Approval.contract_id == c.id).first():
                # Leave the risky contract in pending so the demo can show
                # manual approval routing in the UI.
                leave_pending = "Quantum" in (c.counterparty or "")
                _start_workflow_for(db, c, users, leave_pending=leave_pending)

        print("Done.")
        print("\nDemo credentials (password: Demo1234!):")
        for u in USERS:
            print(f"  {u['email']} ({u['role']})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
