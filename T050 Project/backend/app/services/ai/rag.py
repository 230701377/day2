"""
RAG (Retrieval Augmented Generation) for contract Q&A.

Implements a vector-over-pgvector retrieval layer:
1. Embeds the user question with the local TF-IDF encoder (same model used
   at index time so vectors live in the same space).
2. Cosine-similarity ranks all clauses the user is authorized to access.
3. Top-k excerpts are passed to the LLM (or the deterministic fallback) with
   a hardened system prompt that prohibits instruction-following from the
   context.
4. The answer is returned together with clause-level citations and a
   confidence score. No answer is invented outside the retrieved excerpts.
"""
from typing import List, Dict, Optional

import numpy as np
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from app.models.models import Clause, Contract
from app.services.ai.embeddings import encode, cosine
from app.services.ai.llm import generate_answer, sanitize


def _user_can_read(user, contract: Contract) -> bool:
    if user.role == "admin":
        return True
    if user.role == "requester":
        return contract.owner_id == user.id
    return True  # legal/finance/manager/compliance/executive read all


import re
from collections import Counter


def _bm25_lexical_score(query: str, text: str) -> float:
    """Compute BM25-lite keyword match score."""
    q_tokens = set(re.findall(r"[A-Za-z0-9_\-]+", query.lower()))
    q_tokens -= {"the", "a", "an", "of", "to", "is", "are", "what", "how", "does", "this", "that", "in", "on", "for", "and", "or"}
    if not q_tokens or not text:
        return 0.0
    text_lower = text.lower()
    t_tokens = re.findall(r"[A-Za-z0-9_\-]+", text_lower)
    counts = Counter(t_tokens)
    doc_len = len(t_tokens)
    k1 = 1.5
    b = 0.75
    avg_len = 150.0
    score = 0.0
    for q in q_tokens:
        tf = counts.get(q, 0)
        if tf > 0:
            num = tf * (k1 + 1)
            den = tf + k1 * (1 - b + b * (doc_len / avg_len))
            score += (num / den)
    return score


def retrieve_clauses(db: Session, user, question: str, contract_ids: Optional[List[str]],
                      top_k: int = 5) -> List[Dict]:
    """
    Hybrid RAG Retrieval Layer:
    Combines Dense Vector Similarity (pgvector) + BM25 Lexical Keyword Search using Reciprocal Rank Fusion (RRF).
    """
    clean_q = sanitize(question, max_len=2000)
    q_vec = encode([clean_q])[0]

    stmt = select(Clause, Contract).join(Contract, Clause.contract_id == Contract.id)
    if contract_ids:
        stmt = stmt.where(Clause.contract_id.in_(contract_ids))
    if user.role == "requester":
        stmt = stmt.where(Contract.owner_id == user.id)

    rows = db.execute(stmt).all()
    if not rows:
        return []

    # 1. Rank by Dense Vector Similarity
    dense_scores = []
    # 2. Rank by BM25 Lexical Similarity
    lexical_scores = []

    candidates = []
    for clause, contract in rows:
        if not _user_can_read(user, contract):
            continue
        emb = clause.embedding
        d_score = cosine(np.asarray(emb, dtype=np.float32), q_vec) if emb is not None else 0.0
        l_score = _bm25_lexical_score(clean_q, (clause.heading or "") + " " + (clause.body or ""))
        candidates.append((clause, contract, d_score, l_score))

    # Dense sorting
    dense_sorted = sorted(candidates, key=lambda x: x[2], reverse=True)
    dense_ranks = {item[0].id: rank + 1 for rank, item in enumerate(dense_sorted)}

    # Lexical sorting
    lexical_sorted = sorted(candidates, key=lambda x: x[3], reverse=True)
    lexical_ranks = {item[0].id: rank + 1 for rank, item in enumerate(lexical_sorted)}

    # 3. Reciprocal Rank Fusion (RRF)
    k_rrf = 60
    rrf_scored = []
    for clause, contract, d_score, l_score in candidates:
        r_dense = dense_ranks[clause.id]
        r_lexical = lexical_ranks[clause.id]
        rrf_score = (1.0 / (k_rrf + r_dense)) + (1.0 / (k_rrf + r_lexical))
        rrf_scored.append((rrf_score, clause, contract, d_score, l_score))

    rrf_scored.sort(key=lambda x: x[0], reverse=True)

    out = []
    for rrf_score, clause, contract, d_score, l_score in rrf_scored[:top_k]:
        out.append({
            "contract_id": contract.id,
            "contract_title": contract.title,
            "clause_id": clause.id,
            "heading": clause.heading or clause.clause_number,
            "page_number": clause.page_number,
            "body": clause.body,
            "score": round(float(d_score if d_score > 0 else rrf_score * 10), 3),
            "rrf_score": round(float(rrf_score), 4),
            "dense_score": round(float(d_score), 3),
            "lexical_score": round(float(l_score), 3),
        })
    return out


def answer_question(db: Session, user, question: str,
                     contract_ids: Optional[List[str]] = None,
                     top_k: int = 5) -> Dict:
    blocks = retrieve_clauses(db, user, question, contract_ids=contract_ids, top_k=top_k)
    if not blocks:
        return {
            "question": question,
            "answer": "No authorized contract content was found that matches your question.",
            "sources": [],
            "confidence": 0.0,
        }
    result = generate_answer(question, blocks)
    confidence = float(np.mean([b["score"] for b in blocks])) if blocks else 0.0
    result["sources"] = [
        {
            "contract_id": b["contract_id"],
            "contract_title": b["contract_title"],
            "clause_id": b["clause_id"],
            "heading": b["heading"],
            "page_number": b["page_number"],
            "excerpt": (b["body"][:300] + ("..." if len(b["body"]) > 300 else "")),
            "score": b["score"],
        }
        for b in blocks
    ]
    result["confidence"] = round(confidence, 3)
    result["question"] = question
    return result
