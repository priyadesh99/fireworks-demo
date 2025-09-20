# validators.py
from datetime import date, datetime
import unicodedata
import re
import os
import json
from extract import FireworksLLM



def _normalize_name(name: str | None) -> list[str]:
    if not name:
        return []
    text = unicodedata.normalize("NFKD", name).lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    tokens = [t for t in text.split() if t]
    return tokens


def _parse_date(s: str | None):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def validate_required_fields_passport(d):
    out = []
    # required fields
    for k in ["name", "dob", "expiry_date", "id_number", "issuing_country"]:
        out.append({"name": f"required:{k}", "status": "pass" if d.get(k) else "fail"})
    # expiry
    try:
        out.append({"name": "expiry_future",
                    "status": "pass" if d.get("expiry_date") and d["expiry_date"] >= date.today().isoformat() else "fail"})
    except Exception:
        out.append({"name": "expiry_future", "status": "warn"})
    # age check (>=18)
    try:
        dob = datetime.strptime(d.get("dob", ""), "%Y-%m-%d").date()
        age = (date.today() - dob).days // 365
        out.append({"name": "age_check", "status": "pass" if age >= 18 else "fail"})
    except Exception:
        out.append({"name": "age_check", "status": "warn"})
    return out


def validate_required_fields_drivers_license(d):
    out = []
    # required fields
    for k in ["name", "dob", "expiry_date", "id_number", "issuing_state", "address"]:
        out.append({"name": f"required:{k}", "status": "pass" if d.get(k) else "fail"})
    # expiry
    try:
        out.append({"name": "expiry_future",
                    "status": "pass" if d.get("expiry_date") and d["expiry_date"] >= date.today().isoformat() else "fail"})
    except Exception:
        out.append({"name": "expiry_future", "status": "warn"})
    # age check (>=18)
    try:
        dob = datetime.strptime(d.get("dob", ""), "%Y-%m-%d").date()
        age = (date.today() - dob).days // 365
        out.append({"name": "age_check", "status": "pass" if age >= 18 else "fail"})
    except Exception:
        out.append({"name": "age_check", "status": "warn"})
    return out


def validate_consistency_passport_and_drivers_license(passport: dict, drivers_license: dict):
    """Rule-based consistency check first; if name differs, fall back to an LLM judge.
    Returns a list of validator items compatible with the UI.
    """
    results = []

    # Name consistency (rule-based)
    p_tokens = set(_normalize_name(passport.get("name")))
    d_tokens = set(_normalize_name(drivers_license.get("name")))
    name_rule = bool(p_tokens and d_tokens and p_tokens == d_tokens)

    # DOB consistency (rule-based exact date compare after parsing)
    p_dob = _parse_date(passport.get("dob"))
    d_dob = _parse_date(drivers_license.get("dob"))
    dob_rule = bool(p_dob and d_dob and p_dob == d_dob)

    name_status = "pass" if name_rule else "fail"
    dob_status = "pass" if dob_rule else "fail"

    return [{"name": "consistency:name", "status": name_status}, {"name": "consistency:dob", "status": dob_status}]

    # # LLM fallback only if rule-based failed for name and LLM is available
    # if not name_rule:
    #     try:
    #         llm = FireworksLLM()
    #         prompt = (
    #             "You are verifying if two ID records refer to the same person based ONLY on name.\n"
    #             "Return ONLY JSON: {\"same_person\": true|false}.\n\n"
    #             f"Passport name: {passport.get('name')}\n"
    #             f"License name: {drivers_license.get('name')}\n"
    #             "Consider minor OCR differences, diacritics, and order of tokens equivalent."
    #         )
    #         resp = llm.chat.completions.create(messages=[{"role": "user", "content": prompt}], temperature=0)
    #         verdict = json.loads(resp.choices[0].message.content)
    #         if isinstance(verdict, dict) and isinstance(verdict.get("same_person"), bool):
    #             name_status = "pass" if verdict["same_person"] else "fail"
    #         else:
    #             # If malformed, leave rule-based result
    #             pass
    #     except Exception:
    #         # Ignore LLM errors, keep rule-based result
    #         pass

    # results.append({"name": "consistency:name", "status": name_status})
    # results.append({"name": "consistency:dob", "status": dob_status})
    # return results
   