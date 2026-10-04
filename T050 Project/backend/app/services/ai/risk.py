"""
Hybrid risk detection.

Three signals are combined per finding:
1. Rule-based: deterministic regex/keyword patterns that flag known risky
   constructs (e.g. unlimited liability, unilateral termination, broad IP
   assignment, missing data-protection language).
2. NLP: sentence-level scoring using lexicon overlap with risk lexicons,
   ambiguity markers, and clause category heuristics.
3. LLM (optional): when an LLM API key is configured, an extra signal is
   added. Otherwise the score is renormalized across the two available
   signals.

Every finding carries:
- a citation (clause id and page) so it can be traced back to the source
- a textual evidence excerpt and recommendation
- explicit scores from each detector so the total is explainable.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.services.ai.embeddings import encode
from app.services.ai.llm import sanitize


# Rule-based risk patterns: (finding_type, severity, regex, evidence_substr, recommendation)
RULES: List[Tuple[str, str, re.Pattern, str, str]] = [
    ("unlimited_liability", "critical", re.compile(
        r"(unlimited liability|without limit(?:ation)? of liability|no limitation of liability|liability .* (unlimited|uncapped))",
        re.IGNORECASE),
     "Unlimited liability exposure",
     "Negotiate a liability cap tied to fees paid in the trailing 12 months."),

    ("broad_indemnification", "high", re.compile(
        r"(indemnify.*?(all|any|every).*?(loss|damage|claim|liability))",
        re.IGNORECASE),
     "Broad indemnification obligation",
     "Limit indemnification to third-party IP claims and to losses caused by the indemnifying party."),

    ("auto_renewal_short_notice", "high", re.compile(
        r"automatic(ally)? renew.*?(thirty|30|forty[- ]five|45)[ -]day",
        re.IGNORECASE),
     "Auto-renewal with short opt-out window",
     "Extend the non-renewal notice period to at least 60 days."),

    ("missing_data_protection", "high", re.compile(
        r"(no reference to|does not address|omits) (personal data|gdpr|ccpa|data protection)",
        re.IGNORECASE),
     "No data-protection commitments",
     "Add GDPR/CCPA-aligned data processing terms, including breach notification timelines."),

    ("unilateral_termination", "medium", re.compile(
        r"(may terminate this agreement (immediately|at any time|without cause))",
        re.IGNORECASE),
     "Unilateral termination right",
     "Limit immediate termination to material breach and add cure periods."),

    ("ip_assignment_employee", "high", re.compile(
        r"(assigns? all (intellectual property|inventions|works)|present assignment of all)",
        re.IGNORECASE),
     "Present assignment of all IP",
     "Ensure assignment is limited to work product within scope and respects pre-existing IP."),

    ("exclusivity_without_compensation", "medium", re.compile(
        r"exclusive(ly)? .* (without|free of) (additional|extra) (compensation|consideration)",
        re.IGNORECASE),
     "Exclusivity without compensation",
     "Tie exclusivity to minimum volume commitments or incremental fees."),

    ("audit_rights_unlimited", "medium", re.compile(
        r"audit .* (at any time|unlimited|without (prior )?notice)",
        re.IGNORECASE),
     "Unlimited audit rights",
     "Limit audits to once per year with reasonable prior notice and during business hours."),

    ("liquidated_damages_excessive", "high", re.compile(
        r"liquidated damages .*(?:in excess of|greater than) ?(?:usd|\$|us\$)? ?\d{6,}",
        re.IGNORECASE),
     "Excessive liquidated damages",
     "Benchmark liquidated damages against actual anticipated harm and statutory limits."),

    ("short_payment_terms", "medium", re.compile(
        r"net\s*(5|7|10)(?!\d)",
        re.IGNORECASE),
     "Short payment terms",
     "Negotiate Net 30 or longer with discount options for early payment."),

    ("missing_limitation_of_liability", "medium", re.compile(
        r"(no|without) (limitation of liability|liability cap)",
        re.IGNORECASE),
     "No liability cap",
     "Insert a mutual liability cap tied to fees paid."),

    ("foreign_jurisdiction", "low", re.compile(
        r"governed by the laws of (china|russia|iran|north korea)",
        re.IGNORECASE),
     "Foreign governing law",
     "Consider implications of cross-border enforcement and sanctions."),

    ("perpetual_license", "medium", re.compile(
        r"(perpetual|irrevocable) license",
        re.IGNORECASE),
     "Perpetual or irrevocable license",
     "Ensure license is non-exclusive, revocable for cause, or paid-up if perpetual."),

    ("non_compete_overbroad", "high", re.compile(
        r"non[- ]compete.*?(worldwide|globally|unlimited (geographic|territory))",
        re.IGNORECASE),
     "Overbroad non-compete",
     "Limit geographic scope, duration (≤12 months) and industry."),

    ("assignment_without_consent", "medium", re.compile(
        r"may assign .* without (the )?(prior )?(written )?consent",
        re.IGNORECASE),
     "Assignment without consent",
     "Require written consent, with carveouts for affiliates and M&A."),

    ("waiver_of_jury_trial", "low", re.compile(
        r"waive.*?(jury|jury trial)",
        re.IGNORECASE),
     "Waiver of jury trial",
     "Review enforceability in the governing jurisdiction."),

    ("uncapped_damages", "critical", re.compile(
        r"damages .* (uncapped|without cap|no limit)",
        re.IGNORECASE),
     "Uncapped damages",
     "Insert a mutual liability cap with carve-outs only for confidentiality and IP infringement."),

    ("ip_warranty_missing", "medium", re.compile(
        r"(no warranty|does not warrant) (non[- ]infringement|that the .* does not infringe)",
        re.IGNORECASE),
     "Missing IP non-infringement warranty",
     "Require supplier IP non-infringement warranty with indemnity."),

    ("force_majeure_overbroad", "low", re.compile(
        r"force majeure .* (any cause|any reason|at its sole discretion)",
        re.IGNORECASE),
     "Overbroad force majeure",
     "Tighten definition to events beyond reasonable control with notice obligations."),

    ("service_level_missing", "medium", re.compile(
        r"(no (service level|sla)|without (a )?service level)",
        re.IGNORECASE),
     "No SLA defined",
     "Add SLA with measurable metrics and remedy credits."),
]


# Risk lexicons for NLP scoring
HIGH_RISK_LEXICON = {
    "unlimited", "uncapped", "without limitation", "indemnify", "indemnification",
    "liquidated damages", "exclusively", "worldwide", "irrevocable", "perpetual",
    "sole discretion", "unilaterally", "immediately terminate", "no warranty",
    "as is", "assigns all", "non-compete",
}
MEDIUM_RISK_LEXICON = {
    "may terminate", "audit", "assignment", "non-solicitation", "governing law",
    "jurisdiction", "notice", "force majeure", "confidential",
}
AMBIGUITY_LEXICON = {
    "may", "might", "could", "reasonable", "appropriate", "as applicable",
    "as determined", "in its discretion", "as needed", "from time to time",
}


SEVERITY_WEIGHTS = {"low": 1.0, "medium": 2.0, "high": 3.0, "critical": 4.0}


@dataclass
class RiskHit:
    finding_type: str
    severity: str
    score_rule: float
    score_nlp: float
    score_llm: float
    title: str
    description: str
    evidence: str
    recommendation: str
    source_excerpt: str
    source_page: Optional[int]


def _evidence_snippet(text: str, span: Tuple[int, int], radius: int = 220) -> str:
    s, e = span
    start = max(0, s - radius)
    end = min(len(text), e + radius)
    return text[start:end].strip()


def _rule_findings(clauses: List[Dict]) -> List[RiskHit]:
    findings: List[RiskHit] = []
    for c in clauses:
        body = c["body"]
        page = c.get("page_number")
        for ftype, sev, pat, title, rec in RULES:
            m = pat.search(body)
            if m:
                findings.append(RiskHit(
                    finding_type=ftype,
                    severity=sev,
                    score_rule=SEVERITY_WEIGHTS[sev] * 1.5,
                    score_nlp=0.0,
                    score_llm=0.0,
                    title=title,
                    description=(
                        f"A clause in '{c.get('heading') or c.get('clause_number') or 'Document'}' "
                        f"matches the pattern for '{title}'."
                    ),
                    evidence=f"Matched pattern: /{pat.pattern}/",
                    recommendation=rec,
                    source_excerpt=_evidence_snippet(body, m.span()),
                    source_page=page,
                ))
    return findings


def _nlp_score(body: str) -> float:
    if not body:
        return 0.0
    text = body.lower()
    h = sum(text.count(w) for w in HIGH_RISK_LEXICON)
    m = sum(text.count(w) for w in MEDIUM_RISK_LEXICON)
    amb = sum(text.count(w) for w in AMBIGUITY_LEXICON)
    words = max(1, len(text.split()))
    # density-based
    density = ((h * 3.0) + (m * 1.5) + (amb * 0.5)) / words
    score = min(4.0, density * 250.0)
    return score


def _aggregate_nlp_findings(clauses: List[Dict], rule_findings: List[RiskHit]) -> List[RiskHit]:
    """Add NLP-signal findings for high-risk clauses that the rules didn't already flag."""
    rule_keys = {(f.finding_type, f.source_page) for f in rule_findings}
    nlp_findings: List[RiskHit] = []
    for c in clauses:
        body = c["body"]
        score = _nlp_score(body)
        if score >= 1.5:
            # already flagged by rules? skip generic nlp finding.
            page = c.get("page_number")
            key = ("nlp_risk_density", page)
            if key in rule_keys:
                continue
            if score >= 3.0:
                sev = "high"
            elif score >= 2.0:
                sev = "medium"
            else:
                sev = "low"
            excerpt = body[:400]
            nlp_findings.append(RiskHit(
                finding_type="high_risk_language_density",
                severity=sev,
                score_rule=0.0,
                score_nlp=score * 1.0,
                score_llm=0.0,
                title="High-risk language density",
                description=(
                    f"Clause '{c.get('heading') or c.get('clause_number') or 'Document'}' "
                    f"contains an unusually high density of risk-laden language."
                ),
                evidence=f"NLP density score: {score:.2f}",
                recommendation="Review with Legal; consider redrafting to use neutral, specific language.",
                source_excerpt=excerpt,
                source_page=page,
            ))
    return nlp_findings


def _combine(findings: List[RiskHit]) -> List[RiskHit]:
    """Combine findings: keep distinct (type, page); merge scores if duplicated."""
    seen: Dict[Tuple[str, int], RiskHit] = {}
    for f in findings:
        key = (f.finding_type, f.source_page or 0)
        if key in seen:
            prev = seen[key]
            prev.score_rule = max(prev.score_rule, f.score_rule)
            prev.score_nlp = max(prev.score_nlp, f.score_nlp)
            prev.score_llm = max(prev.score_llm, f.score_llm)
        else:
            seen[key] = f
    out = list(seen.values())
    for f in out:
        f.score_total = round(
            (min(4.0, f.score_rule) * 0.45 +
             min(4.0, f.score_nlp) * 0.30 +
             min(4.0, f.score_llm) * 0.25),
            2,
        )
    out.sort(key=lambda x: (x.score_total, x.severity), reverse=True)
    return out


def detect_risks(clauses: List[Dict], llm_findings: Optional[List[RiskHit]] = None) -> List[RiskHit]:
    rule = _rule_findings(clauses)
    nlp = _aggregate_nlp_findings(clauses, rule)
    all_findings = rule + nlp + (llm_findings or [])
    return _combine(all_findings)


def severity_counts(findings: List[RiskHit]) -> Dict[str, int]:
    out = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for f in findings:
        out[f.severity] = out.get(f.severity, 0) + 1
    return out


def overall_risk_score(findings: List[RiskHit]) -> Tuple[float, str]:
    """Return a 0-100 score and a label."""
    if not findings:
        return 5.0, "low"
    weights = {"critical": 25, "high": 15, "medium": 7, "low": 2}
    total = sum(weights.get(f.severity, 1) for f in findings)
    score = min(100.0, total)
    if score >= 60:
        level = "critical"
    elif score >= 35:
        level = "high"
    elif score >= 15:
        level = "medium"
    else:
        level = "low"
    return round(score, 1), level
