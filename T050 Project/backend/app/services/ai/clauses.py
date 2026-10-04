"""
Clause extraction and classification.

Extraction uses regex-driven heading detection across multiple contract styles
(NDA, MSA, SOW, vendor agreements, etc.) and groups paragraph blocks under
each heading. Classification compares each clause's body against curated
prototype texts for the canonical CUAD-style categories using cosine
similarity over the local TF-IDF embedding space, yielding a confidence
score per assignment.
"""
import re
from typing import Dict, List, Tuple

import numpy as np

from app.services.ai.embeddings import encode, cosine


# Canonical clause categories inspired by CUAD + commercial-contract review
CATEGORIES = [
    "definitions",
    "term",
    "payment_terms",
    "termination",
    "confidentiality",
    "intellectual_property",
    "indemnification",
    "limitation_of_liability",
    "warranty",
    "disclaimer",
    "governing_law",
    "jurisdiction",
    "dispute_resolution",
    "force_majeure",
    "assignment",
    "notices",
    "entire_agreement",
    "amendment",
    "severability",
    "waiver",
    "counterparts",
    "non_compete",
    "non_solicitation",
    "exclusivity",
    "data_protection",
    "audit_rights",
    "insurance",
    "compliance",
    "renewal",
    "auto_renewal",
    "service_levels",
    "acceptance",
    "deliverables",
    "milestones",
    "change_control",
    "pricing",
    "taxes",
    "expenses",
    "signatures",
    "boilerplate",
]


CATEGORY_PROTOTYPES: Dict[str, List[str]] = {
    "definitions": [
        "For the purposes of this Agreement the following terms shall have the meanings set forth below.",
        "Definitions: means and includes the following capitalized terms wherever used in this contract.",
    ],
    "term": [
        "The term of this Agreement shall commence on the Effective Date and continue for a period of twelve months.",
        "This Agreement begins on the Effective Date and shall remain in effect until terminated in accordance with its terms.",
    ],
    "payment_terms": [
        "Customer shall pay all undisputed invoices within thirty days of receipt.",
        "Fees are payable Net 30 from the invoice date. Late payments accrue interest.",
    ],
    "termination": [
        "Either party may terminate this Agreement for material breach upon thirty days written notice.",
        "The Company may terminate this Agreement immediately upon written notice for cause.",
    ],
    "confidentiality": [
        "Each party agrees to maintain the confidentiality of all Confidential Information disclosed by the other party.",
        "Recipient shall protect Confidential Information using the same degree of care it uses for its own confidential information.",
    ],
    "intellectual_property": [
        "All intellectual property rights in the Deliverables shall be owned by the Customer upon full payment.",
        "Provider retains all right, title and interest in and to its pre-existing intellectual property.",
    ],
    "indemnification": [
        "Vendor shall indemnify, defend and hold harmless Customer from any third party claims arising from Vendor's negligence.",
        "Each party shall indemnify the other against losses caused by its breach of this Agreement.",
    ],
    "limitation_of_liability": [
        "In no event shall either party's liability exceed the fees paid in the twelve months preceding the claim.",
        "Neither party shall be liable for any indirect, incidental, special or consequential damages.",
    ],
    "warranty": [
        "Vendor warrants that the Services will be performed in a professional and workmanlike manner.",
        "Provider represents and warrants that the Software will materially conform to the Documentation.",
    ],
    "disclaimer": [
        "Except as expressly set forth herein, the Services are provided 'as is' without any warranty of any kind.",
        "All other warranties, express or implied, are hereby disclaimed to the maximum extent permitted by law.",
    ],
    "governing_law": [
        "This Agreement shall be governed by and construed in accordance with the laws of the State of New York.",
        "The laws of Delaware govern this Agreement without regard to its conflict of laws principles.",
    ],
    "jurisdiction": [
        "The parties consent to the exclusive jurisdiction of the courts located in New York County.",
        "Any action arising under this Agreement shall be brought in the state or federal courts of California.",
    ],
    "dispute_resolution": [
        "Any dispute arising out of this Agreement shall be resolved by binding arbitration administered by JAMS.",
        "The parties shall attempt to resolve disputes through good faith negotiation before commencing litigation.",
    ],
    "force_majeure": [
        "Neither party shall be liable for any failure or delay due to causes beyond its reasonable control.",
        "Force majeure events include acts of God, war, terrorism, pandemic and governmental action.",
    ],
    "assignment": [
        "Neither party may assign this Agreement without the prior written consent of the other party.",
        "Either party may assign this Agreement to an affiliate or in connection with a merger or acquisition.",
    ],
    "notices": [
        "All notices under this Agreement shall be in writing and sent to the addresses set forth above.",
        "Notices shall be delivered by hand, certified mail or recognized overnight courier.",
    ],
    "entire_agreement": [
        "This Agreement constitutes the entire agreement between the parties and supersedes all prior understandings.",
        "This document is the complete and exclusive statement of the agreement between the parties.",
    ],
    "amendment": [
        "No amendment to this Agreement is effective unless made in writing and signed by both parties.",
        "Any modification of this Agreement must be executed by an authorized representative of each party.",
    ],
    "severability": [
        "If any provision of this Agreement is held unenforceable the remaining provisions shall remain in effect.",
        "The invalidity of any provision shall not affect the validity of the remaining provisions.",
    ],
    "waiver": [
        "No failure or delay in exercising any right under this Agreement shall operate as a waiver thereof.",
        "A waiver of any breach shall not constitute a waiver of any subsequent breach.",
    ],
    "counterparts": [
        "This Agreement may be executed in counterparts each of which shall be deemed an original.",
        "This Agreement may be executed in one or more counterparts and by electronic signature.",
    ],
    "non_compete": [
        "During the term and for twelve months thereafter, Vendor shall not compete with the Customer.",
        "The Consultant agrees not to engage in any business that competes with the Company.",
    ],
    "non_solicitation": [
        "Neither party shall solicit the employees of the other during the term and for one year thereafter.",
        "For a period of twelve months, each party agrees not to hire or solicit employees of the other.",
    ],
    "exclusivity": [
        "During the term, Provider shall be the exclusive supplier of the Services to Customer.",
        "Vendor is appointed as the exclusive distributor in the Territory for the term of this Agreement.",
    ],
    "data_protection": [
        "Processor shall implement appropriate technical and organizational measures to protect Personal Data.",
        "The parties shall comply with all applicable data protection laws including GDPR and CCPA.",
    ],
    "audit_rights": [
        "Customer may audit Vendor's books and records relating to this Agreement once per year.",
        "Upon reasonable notice, Customer may inspect Vendor's compliance with security requirements.",
    ],
    "insurance": [
        "Vendor shall maintain commercial general liability insurance with limits not less than $1,000,000.",
        "The Supplier shall carry professional indemnity insurance throughout the term.",
    ],
    "compliance": [
        "Each party shall comply with all applicable laws and regulations in performing under this Agreement.",
        "Vendor represents that it complies with anti-bribery and export control laws.",
    ],
    "renewal": [
        "This Agreement shall automatically renew for successive twelve month terms unless either party gives notice.",
        "Upon expiration the parties may renew this Agreement by mutual written agreement.",
    ],
    "auto_renewal": [
        "This Agreement will automatically renew for additional one-year terms unless terminated in writing.",
        "Failure to provide written notice of non-renewal at least sixty days prior shall result in automatic renewal.",
    ],
    "service_levels": [
        "Vendor shall maintain a monthly uptime of 99.9 percent for the hosted service.",
        "Service level credits shall be issued for failure to meet the agreed service levels.",
    ],
    "acceptance": [
        "Customer shall have thirty days to accept or reject the Deliverables following delivery.",
        "Deliverables are deemed accepted unless Customer provides written notice of rejection within the review period.",
    ],
    "deliverables": [
        "Vendor shall deliver the items specified in Schedule A in accordance with the milestones set forth herein.",
        "The Deliverables include all software, documentation and training materials described in this Agreement.",
    ],
    "milestones": [
        "The project shall be completed according to the milestones set forth in Schedule B.",
        "Each milestone has an associated due date and acceptance criteria.",
    ],
    "change_control": [
        "Any change to the scope of work must be documented in a signed change order.",
        "Changes to the Services require a written change request approved by both parties.",
    ],
    "pricing": [
        "Customer shall pay the fees set forth in Schedule A.",
        "Pricing is subject to an annual increase not to exceed the Consumer Price Index.",
    ],
    "taxes": [
        "Customer is responsible for all sales, use and value added taxes associated with the Services.",
        "Each party shall bear its own taxes except as required by law.",
    ],
    "expenses": [
        "Pre-approved reasonable out of pocket expenses shall be reimbursed by Customer.",
        "Travel and lodging expenses shall be reimbursed at cost without markup.",
    ],
    "signatures": [
        "IN WITNESS WHEREOF the parties have executed this Agreement as of the Effective Date.",
        "Signed by the duly authorized representatives of the parties.",
    ],
    "boilerplate": [
        "Headings are for convenience only and shall not affect interpretation.",
        "This Agreement may be executed in counterparts and by electronic signature.",
    ],
}


# Heading regex patterns - covers most common legal styles
HEADING_PATTERNS = [
    re.compile(r"^(?P<num>(?:\d+\.)+\d*|\d+\)|\d+|Section\s+\d+|Article\s+[IVXLCDM]+)\s*[\.\):\-]?\s*(?P<title>[A-Z][A-Za-z ,\-\(\)\&\.]{2,80})$"),
    re.compile(r"^(?P<title>(?:Definitions|Term|Payment\s+Terms?|Termination|Confidentiality|Intellectual\s+Property|Indemnification|Limitation\s+of\s+Liability|Warrant(y|ies)|Disclaimer|Governing\s+Law|Jurisdiction|Dispute\s+Resolution|Force\s+Majeure|Assignment|Notices|Entire\s+Agreement|Amendment|Severability|Waiver|Counterparts|Non[- ]Compete|Non[- ]Solicitation|Exclusivity|Data\s+Protection|Audit\s+Rights?|Insurance|Compliance|Renewal|Auto[- ]?Renewal|Service\s+Levels?|Acceptance|Deliverables|Milestones?|Change\s+Control|Pricing|Taxes|Expenses|Signatures?|Notices?|Boilerplate))\s*[\.\:]?$", re.IGNORECASE),
    re.compile(r"^(?P<title>[A-Z][A-Z0-9 ,\-/\(\)\&]{4,80})\s*[\.\:]?$"),
    re.compile(r"^(?P<title>\d+\.\s+[A-Z][A-Za-z ,\-\&\.]{2,80})$"),
]


# Pre-compute prototype embeddings once
_PROTO_VECS: Dict[str, np.ndarray] = {}


def _ensure_prototypes():
    global _PROTO_VECS
    if _PROTO_VECS:
        return
    for cat, texts in CATEGORY_PROTOTYPES.items():
        vecs = encode(texts)
        mean = vecs.mean(axis=0)
        n = np.linalg.norm(mean)
        if n > 0:
            mean /= n
        _PROTO_VECS[cat] = mean


def _is_heading(line: str) -> Tuple[bool, str]:
    line = line.strip()
    if not line or len(line) > 120:
        return False, ""
    for pat in HEADING_PATTERNS:
        m = pat.match(line)
        if m:
            title = m.group("title") if "title" in m.groupdict() else line
            return True, title.strip()
    return False, ""


def extract_clauses(pages: List[Tuple[int, str]]) -> List[Dict]:
    """Split a document into clauses using heading detection + page attribution."""
    clauses: List[Dict] = []
    current = {"clause_number": "", "heading": "", "body": "", "page_number": 1, "start_offset": 0, "end_offset": 0}
    char_offset = 0

    def flush():
        if current["body"].strip():
            clauses.append({
                "clause_number": current["clause_number"],
                "heading": current["heading"],
                "body": current["body"].strip(),
                "page_number": current["page_number"],
                "start_offset": current["start_offset"],
                "end_offset": current["end_offset"],
            })

    for page_num, page_text in pages:
        if not page_text:
            continue
        lines = page_text.split("\n")
        page_start = char_offset
        page_offset = 0
        for raw in lines:
            line = raw.strip()
            is_head, title = _is_heading(line)
            if is_head and len(current["body"].strip()) > 80:
                flush()
                current = {
                    "clause_number": "",
                    "heading": title,
                    "body": "",
                    "page_number": page_num,
                    "start_offset": page_start + page_offset,
                    "end_offset": page_start + page_offset,
                }
            else:
                if current["body"] == "" and not is_head and line:
                    # implicit heading - first non-empty line on page 1
                    if page_num == 1 and len(line) < 120:
                        current["heading"] = line
                if line:
                    if current["body"]:
                        current["body"] += "\n"
                    current["body"] += line
                current["end_offset"] = page_start + page_offset + len(line)
            page_offset += len(raw) + 1
        char_offset = page_start + len(page_text)
    flush()

    if not clauses and pages:
        full_text = "\n\n".join(p[1] for p in pages)
        clauses.append({
            "clause_number": "",
            "heading": "Document",
            "body": full_text,
            "page_number": 1,
            "start_offset": 0,
            "end_offset": len(full_text),
        })

    # assign numeric indexes for clauses without numbers
    for i, c in enumerate(clauses, start=1):
        if not c["clause_number"]:
            c["clause_number"] = f"{i}"
    return clauses


def classify_clause(body: str) -> Tuple[str, float]:
    """Classify a clause body into a canonical category with a confidence."""
    _ensure_prototypes()
    if not body or len(body.strip()) < 20:
        return "boilerplate", 0.0
    vec = encode([body])[0]
    best_cat = "boilerplate"
    best_score = -1.0
    for cat, pvec in _PROTO_VECS.items():
        s = float(np.dot(vec, pvec))
        if s > best_score:
            best_score = s
            best_cat = cat
    confidence = max(0.0, min(1.0, (best_score + 1.0) / 2.0))
    return best_cat, confidence


def classify_clauses_batch(clauses: List[Dict]) -> List[Tuple[str, float]]:
    return [classify_clause(c["body"]) for c in clauses]
