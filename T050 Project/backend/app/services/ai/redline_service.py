"""
AI Autonomous Redlining & Counter-Proposal Service.

Scans legal contract clauses for high-risk provisions, generates compliant enterprise counter-proposals,
and calculates character/word-level diffs.
"""
import re
import difflib
from typing import List, Dict, Any


class RedlineService:
    """
    Automated Redlining Engine for Contract Mitigation & Counter-Proposals.
    """

    RULES = [
        {
            "risk_type": "Unlimited Liability",
            "pattern": r"(unlimited|uncapped|no limit|without limitation).*(liability|damages)",
            "rationale": "Unlimited liability exposes the organization to unbounded financial risk.",
            "replacement": "In no event shall either party's aggregate liability under this Agreement exceed the total fees paid or payable in the twelve (12) months preceding the claim."
        },
        {
            "risk_type": "Uncapped Price Increase",
            "pattern": r"(increase|jump|raise).*(price|fees|rate).*(automatically|\d+%)",
            "rationale": "Automatic fee increases without price caps create budget volatility.",
            "replacement": "Fees may be adjusted upon annual renewal with sixty (60) days written notice, provided such increase shall not exceed 3% or the Consumer Price Index (CPI), whichever is lower."
        },
        {
            "risk_type": "Broad Indemnification",
            "pattern": r"indemnify.*(any|all)\s*(claims|losses|damages)",
            "rationale": "Overly broad indemnification shifts third-party liabilities without negligence thresholds.",
            "replacement": "Each party agrees to indemnify, defend, and hold harmless the other party from third-party claims arising directly from its gross negligence or willful misconduct."
        },
        {
            "risk_type": "Short Termination Notice Window",
            "pattern": r"terminate.*(5|7|10|14)\s*days",
            "rationale": "Short termination windows create operational disruption risks.",
            "replacement": "Either party may terminate this Agreement for convenience upon providing at least thirty (30) days prior written notice."
        }
    ]

    @staticmethod
    def generate_redlines(clauses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        redlines = []
        for c in clauses:
            body = c.get("body", "")
            heading = c.get("heading") or c.get("clause_number") or "Clause"
            page_num = c.get("page_number", 1)

            for rule in RedlineService.RULES:
                if re.search(rule["pattern"], body, re.IGNORECASE):
                    proposed = rule["replacement"]
                    diff = RedlineService._compute_diff(body, proposed)
                    redlines.append({
                        "clause_id": c.get("id"),
                        "heading": heading,
                        "page_number": page_num,
                        "risk_type": rule["risk_type"],
                        "rationale": rule["rationale"],
                        "original_text": body,
                        "proposed_text": proposed,
                        "diff_summary": diff["diff_summary"],
                        "diff_html": diff["diff_html"]
                    })
                    break
        return redlines

    @staticmethod
    def _compute_diff(original: str, proposed: str) -> Dict[str, Any]:
        d = difflib.Differ()
        orig_words = original.split()
        prop_words = proposed.split()
        diff_res = list(d.compare(orig_words, prop_words))

        html_parts = []
        for word in diff_res:
            if word.startswith("- "):
                html_parts.append(f'<span style="background-color: #fee2e2; color: #dc2626; text-decoration: line-through;">{word[2:]}</span>')
            elif word.startswith("+ "):
                html_parts.append(f'<span style="background-color: #dcfce7; color: #16a34a; font-weight: 600;">{word[2:]}</span>')
            elif word.startswith("  "):
                html_parts.append(word[2:])

        diff_html = " ".join(html_parts)
        diff_summary = f"{len([w for w in diff_res if w.startswith('- ')])} deletions, {len([w for w in diff_res if w.startswith('+ ')])} additions"
        return {"diff_html": diff_html, "diff_summary": diff_summary}


redline_service = RedlineService()
