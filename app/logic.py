import re

PATTERNS = [
    ("turnover", r".{0,100}(?:annual average turnover|average annual turnover|minimum turnover|annual turnover|turnover of).{0,180}"),
    ("experience", r".{0,100}(?:years? of experience|similar work|similar works|completed projects|work experience|experience of at least).{0,180}"),
    ("certification", r".{0,100}(?:ISO\s*[-:]?\s*\d+|BIS|certification|certified|license|licence|registration certificate).{0,180}"),
    ("emd_fee", r".{0,100}(?:earnest money deposit|EMD|bid security|tender fee|processing fee).{0,180}"),
    ("documents", r".{0,100}(?:PAN card|GST registration|GSTIN|audited balance sheet|income tax return|solvency certificate|mandatory documents).{0,180}"),
    ("deadline", r".{0,100}(?:bid submission|submission deadline|last date|closing date|due date).{0,180}"),
    ("technical", r".{0,100}(?:technical specification|technical eligibility|technical qualification|manufacturer authorization|warranty).{0,180}"),
]

def extract_requirements(text):
    findings, seen = [], set()
    for category, pattern in PATTERNS:
        for m in re.finditer(pattern, text or "", re.I):
            excerpt = re.sub(r"\s+", " ", m.group(0)).strip(" .\n\t")
            key = (category, excerpt.lower())
            if len(excerpt) >= 18 and key not in seen:
                seen.add(key)
                findings.append({"category": category, "requirement_text": excerpt, "source": "Extracted tender text", "page": None, "confidence": "low"})
            if len(findings) >= 60:
                return findings
    return findings

def compare(requirements, company):
    out = []
    for req in requirements:
        category, text = req["category"], req["requirement_text"]
        status, reason = "Needs manual verification", "The MVP cannot reliably determine this condition from the available profile data."
        if category == "turnover":
            nums = re.findall(r"(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(crore|cr|lakh|lac)?", text, re.I)
            threshold = None
            if nums:
                try:
                    n, unit = nums[-1]
                    threshold = float(n.replace(",", "")) * (10000000 if unit.lower() in ("crore","cr") else 100000 if unit.lower() in ("lakh","lac") else 1)
                except (ValueError, IndexError):
                    pass
            value = company.get("annual_turnover")
            if threshold is not None and isinstance(value, (int,float)):
                status = "Appears satisfied" if value >= threshold else "Potential mismatch"
                reason = "Numeric comparison only. Verify units, financial year, averaging period, currency and exemptions."
            else:
                status = "Missing evidence" if value is None else "Needs manual verification"
                reason = "Confirm the exact threshold and financial period in the original clause."
        elif category == "experience":
            m = re.search(r"(\d+)\s*(?:years?|yrs?)", text, re.I)
            years = company.get("years_experience")
            if m and isinstance(years, (int,float)):
                status = "Appears satisfied" if years >= float(m.group(1)) else "Potential mismatch"
                reason = "Verify whether the tender requires similar-project experience rather than general company age."
            else:
                status = "Missing evidence" if years is None else "Needs manual verification"
                reason = "Specific similar-work requirements need manual verification."
        elif category == "certification":
            certs = str(company.get("certifications") or "").lower()
            codes = re.findall(r"\b[A-Z][A-Z0-9-]{2,}\b", text)
            if codes and any(code.lower() in certs for code in codes):
                status, reason = "Appears satisfied", "Possible match found; verify validity, scope and issuing body."
            else:
                status, reason = "Missing evidence", "No clear matching certification found in profile. This does not prove the company lacks it."
        action = ("Verify the clause, units and any exemptions with the tender authority or a qualified professional."
                  if status == "Potential mismatch" else
                  "Check whether the company has the evidence and add verified details."
                  if status == "Missing evidence" else
                  "Review the original clause and supporting evidence before deciding whether this requirement is met.")
        out.append({**req, "status": status, "reason": reason, "recommended_action": action})
    return out
