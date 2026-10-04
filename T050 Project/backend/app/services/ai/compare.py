"""Semantic version comparison - clause-level diff with risk impact."""
from typing import Dict, List, Tuple

import numpy as np

from app.services.ai.embeddings import encode, cosine
from app.services.ai.risk import overall_risk_score


def _norm(c: Dict) -> str:
    return (c.get("heading") or c.get("clause_number") or "").strip().lower()


def compare_versions(prev_clauses: List[Dict], curr_clauses: List[Dict]) -> Dict:
    """Return a structured diff using category + heading identity and
    embedding-based similarity to flag modified clauses."""
    prev_by_id: Dict[str, Dict] = {_norm(c): c for c in prev_clauses}
    curr_by_id: Dict[str, Dict] = {_norm(c): c for c in curr_clauses}

    added, removed, modified = [], [], []
    common_keys = set(prev_by_id.keys()) & set(curr_by_id.keys())
    only_in_prev = set(prev_by_id.keys()) - set(curr_by_id.keys())
    only_in_curr = set(curr_by_id.keys()) - set(prev_by_id.keys())

    for k in common_keys:
        prev = prev_by_id[k]
        curr = curr_by_id[k]
        if (prev["body"].strip() != curr["body"].strip()):
            pvec = encode([prev["body"]])[0]
            cvec = encode([curr["body"]])[0]
            sim = cosine(pvec, cvec)
            modified.append({
                "clause_number": curr.get("clause_number") or prev.get("clause_number"),
                "heading": curr.get("heading") or prev.get("heading"),
                "from_page": prev.get("page_number"),
                "to_page": curr.get("page_number"),
                "similarity": round(sim, 3),
                "risk_changed": prev.get("risk_level") != curr.get("risk_level"),
                "preview": {
                    "from": prev["body"][:240],
                    "to": curr["body"][:240],
                },
            })

    # Use embedding similarity to recover re-ordered/moved clauses
    if only_in_prev and only_in_curr:
        prev_unmatched = [prev_by_id[k] for k in only_in_prev]
        curr_unmatched = [curr_by_id[k] for k in only_in_curr]
        if prev_unmatched and curr_unmatched:
            pmat = encode([c["body"] for c in prev_unmatched])
            cmat = encode([c["body"] for c in curr_unmatched])
            used_curr = set()
            for i, p in enumerate(prev_unmatched):
                best_j, best_s = -1, -1.0
                for j, _ in enumerate(curr_unmatched):
                    if j in used_curr:
                        continue
                    s = cosine(pmat[i], cmat[j])
                    if s > best_s:
                        best_s = s
                        best_j = j
                if best_j >= 0 and best_s >= 0.7:
                    modified.append({
                        "clause_number": curr_unmatched[best_j].get("clause_number"),
                        "heading": curr_unmatched[best_j].get("heading"),
                        "from_page": p.get("page_number"),
                        "to_page": curr_unmatched[best_j].get("page_number"),
                        "similarity": round(best_s, 3),
                        "risk_changed": p.get("risk_level") != curr_unmatched[best_j].get("risk_level"),
                        "preview": {
                            "from": p["body"][:240],
                            "to": curr_unmatched[best_j]["body"][:240],
                        },
                    })
                    used_curr.add(best_j)

    for k in only_in_prev:
        if not any(m["heading"] == (prev_by_id[k].get("heading") or prev_by_id[k].get("clause_number")) for m in modified):
            removed.append({
                "clause_number": prev_by_id[k].get("clause_number"),
                "heading": prev_by_id[k].get("heading"),
                "page": prev_by_id[k].get("page_number"),
                "preview": prev_by_id[k]["body"][:240],
            })

    for k in only_in_curr:
        if not any(m["heading"] == (curr_by_id[k].get("heading") or curr_by_id[k].get("clause_number")) for m in modified):
            added.append({
                "clause_number": curr_by_id[k].get("clause_number"),
                "heading": curr_by_id[k].get("heading"),
                "page": curr_by_id[k].get("page_number"),
                "preview": curr_by_id[k]["body"][:240],
            })

    # Risk delta
    _, prev_score = overall_risk_score([])
    # We don't have findings from DB in this function; risk_delta is computed
    # by the caller using stored RiskFinding rows. We compute a textual summary here.
    summary_lines = []
    if added:
        summary_lines.append(f"{len(added)} clause(s) added.")
    if removed:
        summary_lines.append(f"{len(removed)} clause(s) removed.")
    if modified:
        summary_lines.append(f"{len(modified)} clause(s) modified.")
    if not summary_lines:
        summary_lines.append("No meaningful textual changes between the two versions.")

    return {
        "added_clauses": added,
        "removed_clauses": removed,
        "modified_clauses": modified,
        "risk_delta": 0.0,  # populated by caller
        "summary": " ".join(summary_lines),
    }
