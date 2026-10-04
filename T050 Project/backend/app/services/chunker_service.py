"""
Semantic Chunker Service.

AI & Document Intelligence Layer — Contextual Clause & Section Chunker.
Splits contract documents into semantically coherent blocks mapped to canonical legal domain topics.
Prepares pgvector metadata vectors for semantic search and RAG retrieval.
"""
import uuid
import re
from typing import List, Dict, Any, Tuple


class SemanticChunkerService:
    """
    Contextual Semantic Chunker for Legal & Commercial Contracts.
    Features:
    - Contextual Clause Segmentation (Preamble, Payment, Liability, Termination, Renewal, Confidentiality, IP, SLA, Governing Law)
    - Semantic boundary detection using heading regex & topic patterns
    - Vector metadata preparation for pgvector store
    """

    SECTIONS = [
        ("Preamble & Parties", r"(agreement|contract|made between|by and between|entered into|parties)"),
        ("Payment Terms & Invoicing", r"(payment|fee|invoice|price|remittance|usd|billing|net \d+|reimbursement)"),
        ("Liability & Indemnification", r"(liabil|indemnif|damages|limitation of liability|hold harmless|claim)"),
        ("Termination & Notice", r"(terminat|cancel|expiration|written notice|end date|cure period)"),
        ("Renewal Window & Terms", r"(renew|auto-renewal|extension|notice window|successive term)"),
        ("Confidentiality & Compliance", r"(confidenti|disclos|audit|soc2|privacy|governance|non-disclosure)"),
        ("Intellectual Property & Licensing", r"(intellectual property|copyright|trademark|patent|license grant|saas|software)"),
        ("Service Level Agreement & SLA", r"(uptime|service level|sla|maintenance|availability|support response)"),
        ("Governing Law & Jurisdiction", r"(governing law|jurisdiction|venue|courts of|choice of law|arbitration|dispute resolution)")
    ]

    @staticmethod
    def chunk_contract(contract_id: str, raw_text: str) -> List[Dict[str, Any]]:
        """
        Segment raw contract text into contextual semantic chunks with metadata for pgvector.
        """
        paragraphs = [p.strip() for p in raw_text.split("\n") if p.strip()]
        chunks = []
        chunk_idx = 0

        for p_index, paragraph in enumerate(paragraphs):
            matched_section = "General Terms & Clauses"
            for s_name, s_pattern in SemanticChunkerService.SECTIONS:
                if re.search(s_pattern, paragraph, re.IGNORECASE):
                    matched_section = s_name
                    break

            page_est = (p_index // 3) + 1

            chunk_obj = {
                "id": str(uuid.uuid4()),
                "contract_id": contract_id,
                "chunk_index": chunk_idx,
                "section_name": matched_section,
                "chunk_text": paragraph,
                "character_count": len(paragraph),
                "token_count_estimate": max(1, len(paragraph) // 4),
                "page_number": page_est,
                "embedding_status": "pgvector_ready"
            }
            chunks.append(chunk_obj)
            chunk_idx += 1

        if not chunks:
            chunks.append({
                "id": str(uuid.uuid4()),
                "contract_id": contract_id,
                "chunk_index": 0,
                "section_name": "Full Document Text",
                "chunk_text": raw_text[:500],
                "character_count": len(raw_text[:500]),
                "token_count_estimate": max(1, len(raw_text[:500]) // 4),
                "page_number": 1,
                "embedding_status": "pgvector_ready"
            })

        return chunks

    @staticmethod
    def semantic_chunk_pages(pages: List[Tuple[int, str]], contract_id: str = "") -> List[Dict[str, Any]]:
        """
        Perform page-attributed semantic chunking over extracted page tuples.
        """
        chunks = []
        chunk_idx = 0

        for page_num, page_content in pages:
            if not page_content.strip():
                continue
            paras = [p.strip() for p in page_content.split("\n") if p.strip()]
            for paragraph in paras:
                matched_section = "General Terms & Clauses"
                for s_name, s_pattern in SemanticChunkerService.SECTIONS:
                    if re.search(s_pattern, paragraph, re.IGNORECASE):
                        matched_section = s_name
                        break

                chunk_obj = {
                    "id": str(uuid.uuid4()),
                    "contract_id": contract_id,
                    "chunk_index": chunk_idx,
                    "section_name": matched_section,
                    "chunk_text": paragraph,
                    "character_count": len(paragraph),
                    "token_count_estimate": max(1, len(paragraph) // 4),
                    "page_number": page_num,
                    "embedding_status": "pgvector_ready"
                }
                chunks.append(chunk_obj)
                chunk_idx += 1

        return chunks


chunker_service = SemanticChunkerService()
