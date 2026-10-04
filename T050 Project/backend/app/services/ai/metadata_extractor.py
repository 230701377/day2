"""
Contract Metadata and Party Extraction Service.

Extracts structured contract metadata (counterparty, financial value, currency,
effective date, expiration date, auto-renewal, notice period, and contract type)
using heuristic regex analysis and LLM enhancements.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
import dateutil.parser


def extract_contract_metadata_complete(text: str, filename: str = "") -> Dict[str, Any]:
    """
    Extracts all metadata fields required for CLM Contract record from full document text.
    Returns:
        {
            "counterparty": str or None,
            "value_amount": float or None,
            "value_currency": str or None,
            "effective_date": datetime or None,
            "expiration_date": datetime or None,
            "auto_renew": bool,
            "renewal_notice_days": int or None,
            "contract_type": str,
            "classification_confidence": float,
            "classification_reason": str,
        }
    """
    result: Dict[str, Any] = {
        "counterparty": None,
        "value_amount": None,
        "value_currency": None,
        "effective_date": None,
        "expiration_date": None,
        "auto_renew": False,
        "renewal_notice_days": None,
        "contract_type": "vendor",
        "classification_confidence": 0.85,
        "classification_reason": "Rule-based pattern classification",
    }

    if not text:
        return result

    # 1. COUNTERPARTY EXTRACTION
    party_patterns = [
        r"(?:by and between|between|entered into by)\s+([A-Z0-9][A-Za-z0-9\s,\.\&]{2,60}?)(?:\s*,|\s+and|\s+with|\s*\(\")",
        r"Vendor[:\s]+([A-Z0-9][A-Za-z0-9\s,\.\&]{2,60})",
        r"Supplier[:\s]+([A-Z0-9][A-Za-z0-9\s,\.\&]{2,60})",
        r"Customer[:\s]+([A-Z0-9][A-Za-z0-9\s,\.\&]{2,60})",
        r"Client[:\s]+([A-Z0-9][A-Za-z0-9\s,\.\&]{2,60})",
        r"Partner[:\s]+([A-Z0-9][A-Za-z0-9\s,\.\&]{2,60})",
        r"Contractor[:\s]+([A-Z0-9][A-Za-z0-9\s,\.\&]{2,60})",
        r"Licensor[:\s]+([A-Z0-9][A-Za-z0-9\s,\.\&]{2,60})",
    ]
    for p in party_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            cand = m.group(1).strip().rstrip(".,;")
            # Filter generic words
            if cand.lower() not in {"the company", "the client", "the vendor", "each party", "the undersigned", "party a", "party b"}:
                if len(cand) > 3:
                    result["counterparty"] = cand
                    break

    # 2. CONTRACT VALUE AND CURRENCY EXTRACTION
    val_patterns = [
        r"(?:total (?:contract )?value|contract price|total fee|purchase price|compensation|total amount|value of)[:\s]*([\$€£]?\s*[\d,]+(?:\.\d{2})?\s*(?:USD|EUR|GBP|CAD|AUD)?)",
        r"([\$€£]\s*[\d,]{3,}(?:\.\d{2})?)",
        r"([\d,]{3,}(?:\.\d{2})?\s*(?:USD|EUR|GBP|dollars))",
        r"fee of\s+([\$€£]?\s*[\d,]+(?:\.\d{2})?)",
    ]
    for vp in val_patterns:
        m = re.search(vp, text, re.IGNORECASE)
        if m:
            raw_val = m.group(1).strip()
            # Detect currency
            curr = "USD"
            if "€" in raw_val or "EUR" in raw_val:
                curr = "EUR"
            elif "£" in raw_val or "GBP" in raw_val:
                curr = "GBP"
            elif "CAD" in raw_val:
                curr = "CAD"
            elif "AUD" in raw_val:
                curr = "AUD"

            # Clean numeric string
            num_str = re.sub(r"[^\d\.]", "", raw_val)
            try:
                val_float = float(num_str)
                if val_float > 0:
                    result["value_amount"] = val_float
                    result["value_currency"] = curr
                    break
            except Exception:
                pass

    # 3. EFFECTIVE DATE (START DATE)
    eff_patterns = [
        r"effective date[:\s]+([A-Za-z0-9,\s/]{6,30})",
        r"commencement date[:\s]+([A-Za-z0-9,\s/]{6,30})",
        r"start date[:\s]+([A-Za-z0-9,\s/]{6,30})",
        r"dated (?:as of|effective)?\s*([A-Za-z0-9,\s/]{6,30})",
        r"made (?:and entered into)?\s+as of\s+([A-Za-z0-9,\s/]{6,30})",
    ]
    for ep in eff_patterns:
        m = re.search(ep, text, re.IGNORECASE)
        if m:
            date_str = m.group(1).strip().rstrip(".,;")
            dt = _parse_date_string(date_str)
            if dt:
                result["effective_date"] = dt
                break

    # 4. EXPIRATION DATE (END DATE)
    exp_patterns = [
        r"expiration date[:\s]+([A-Za-z0-9,\s/]{6,30})",
        r"expires? on[:\s]+(?:the\s+)?([A-Za-z0-9,\s/]{6,30})",
        r"term ends?[:\s]+(?:on\s+)?([A-Za-z0-9,\s/]{6,30})",
        r"termination date[:\s]+([A-Za-z0-9,\s/]{6,30})",
        r"end date[:\s]+([A-Za-z0-9,\s/]{6,30})",
    ]
    for exp_p in exp_patterns:
        m = re.search(exp_p, text, re.IGNORECASE)
        if m:
            date_str = m.group(1).strip().rstrip(".,;")
            dt = _parse_date_string(date_str)
            if dt:
                result["expiration_date"] = dt
                break

    # If expiration date not explicitly found, try calculating from term duration
    if not result["expiration_date"] and result["effective_date"]:
        term_m = re.search(r"(?:term of|period of)\s+(\d+)\s*(year|month|day)s?\s*(?:from|after)", text, re.IGNORECASE)
        if term_m:
            num = int(term_m.group(1))
            unit = term_m.group(2).lower()
            start_dt = result["effective_date"]
            if unit.startswith("year"):
                result["expiration_date"] = start_dt.replace(year=start_dt.year + num)
            elif unit.startswith("month"):
                result["expiration_date"] = start_dt + timedelta(days=30 * num)
            elif unit.startswith("day"):
                result["expiration_date"] = start_dt + timedelta(days=num)

    # 5. RENEWAL EXTRACTION
    if re.search(r"(?:auto-renew|automatically renew|automatic renewal|renew automatically)", text, re.IGNORECASE):
        result["auto_renew"] = True

    notice_m = re.search(r"(\d+)\s*days?\s*(?:prior|written)?\s*(?:notice|written notice)", text, re.IGNORECASE)
    if notice_m:
        try:
            result["renewal_notice_days"] = int(notice_m.group(1))
        except Exception:
            pass

    # 6. CONTRACT TYPE CLASSIFICATION
    t_lower = text.lower() + " " + filename.lower()
    if "non-disclosure" in t_lower or "confidentiality agreement" in t_lower or "nda" in t_lower:
        result["contract_type"] = "nda"
        result["classification_reason"] = "Document contains non-disclosure / confidentiality terms"
    elif "supplier" in t_lower or "supply agreement" in t_lower or "supply of goods" in t_lower:
        result["contract_type"] = "supplier"
        result["classification_reason"] = "Identified supplier / goods supply relationship"
    elif "customer" in t_lower or "client agreement" in t_lower or "sales agreement" in t_lower:
        result["contract_type"] = "customer"
        result["classification_reason"] = "Identified customer / client service relationship"
    elif "partner" in t_lower or "teaming agreement" in t_lower or "joint venture" in t_lower or "partnership" in t_lower:
        result["contract_type"] = "business_partner"
        result["classification_reason"] = "Identified business partner / joint venture relationship"
    elif "master service" in t_lower or "msa" in t_lower:
        result["contract_type"] = "msa"
        result["classification_reason"] = "Master Services Agreement structure detected"
    elif "statement of work" in t_lower or "sow" in t_lower:
        result["contract_type"] = "sow"
        result["classification_reason"] = "Statement of Work structure detected"
    elif "lease" in t_lower or "tenant" in t_lower or "landlord" in t_lower:
        result["contract_type"] = "lease"
        result["classification_reason"] = "Lease / rental agreement detected"
    elif "license" in t_lower or "software license" in t_lower:
        result["contract_type"] = "license"
        result["classification_reason"] = "Software license terms detected"
    elif "employment" in t_lower or "employee" in t_lower or "offer letter" in t_lower:
        result["contract_type"] = "employment"
        result["classification_reason"] = "Employment agreement terms detected"
    else:
        result["contract_type"] = "vendor"
        result["classification_reason"] = "Standard vendor / service provider contract"

    return result


def _parse_date_string(date_str: str) -> Optional[datetime]:
    if not date_str or len(date_str) < 4:
        return None
    # Must contain digits
    if not re.search(r"\d", date_str):
        return None
    try:
        dt = dateutil.parser.parse(date_str, fuzzy=True)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None
