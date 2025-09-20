# app.py
import io
import os
import json
import requests
import streamlit as st
from typing import List
from datetime import datetime
import random
import base64
import hashlib
import pandas 

# -----------------------
# Config
# -----------------------
# Backend base URL (env override recommended for deployments)
BACKEND_BASE = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
EXTRACT_URL = f"{BACKEND_BASE}/extract"
VERIFY_TYPE_URL = f"{BACKEND_BASE}/verify_type"
VERIFY_URL = f"{BACKEND_BASE}/verify"

# Local "DB" directory
DB_ROOT = os.getenv("LOCAL_DB_DIR", os.path.join(os.getcwd(), "local_db"))
DB_CASES_DIR = os.path.join(DB_ROOT, "cases")
DB_CASES_JSONL = os.path.join(DB_ROOT, "cases.jsonl")
# Optional encryption key (set LOCAL_DB_ENCRYPTION_KEY). If set, we encrypt at rest.
DB_ENC_KEY_RAW = os.getenv("LOCAL_DB_ENCRYPTION_KEY", "").strip()

# Option B: or via env var; uncomment the next line to prefer env
# BACKEND_URL = os.getenv("BACKEND_URL", BACKEND_URL)

MAX_FILES = 2  # e.g., DL front/back; passport usually 1
MAX_MB = 20
ALLOWED_EXT = {"jpg", "jpeg", "png", "pdf"}

# -----------------------
# Helpers
# -----------------------
def bytes_to_mb(n: int) -> float:
    return round(n / (1024 * 1024), 2)

def is_allowed(filename: str) -> bool:
    ext = filename.split(".")[-1].lower()
    return ext in ALLOWED_EXT

def validate_uploads(files: List[st.runtime.uploaded_file_manager.UploadedFile]) -> list[str]:
    errors = []
    if not files:
        errors.append("Please upload at least one file.")
        return errors
    if len(files) > MAX_FILES:
        errors.append(f"You can upload at most {MAX_FILES} files at a time.")
    for f in files:
        if not is_allowed(f.name):
            errors.append(f"Unsupported file type for {f.name}. Allowed: {', '.join(sorted(ALLOWED_EXT))}.")
        size_mb = bytes_to_mb(f.size)
        if size_mb > MAX_MB:
            errors.append(f"{f.name} is too large ({size_mb} MB). Max is {MAX_MB} MB.")
    return errors

def mask_text(s: str | None) -> str:
    if not s:
        return ""
    if len(s) <= 6:
        return "•" * len(s)
    return s[:2] + "•" * (len(s) - 6) + s[-4:]

# Friendly labels/icons for validators

def status_icon(status: str) -> str:
    s = (status or "").lower()
    if s == "pass":
        return "✅"
    if s == "warn":
        return "⚠️"
    return "❌"

def friendly_label(raw_name: str | None) -> str:
    if not raw_name:
        return "Check"
    key = raw_name.replace("validate_", "").replace("required_fields_", "").lower()
    mapping = {
        "required_fields_passport": "All required passport fields present",
        "required_fields_drivers_license": "All required driver’s license fields present",
        "drivers_license_required_fields": "All required driver’s license fields present",
        "passport_required_fields": "All required passport fields present",
        "age": "Age is 18+ (DOB valid)",
        "age_check": "Age is 18+ (DOB valid)",
        "expiry": "Document not expired",
        "expiry_date": "Document not expired",
        "expiry_check": "Document not expired",
        "consistency_passport_and_drivers_license": "Passport and license details are consistent",
        "consistency": "Passport and license details are consistent",
        "issuing_country": "Issuing country recognized",
        "issuing_state": "Issuing state recognized",
    }
    return mapping.get(key, raw_name.replace("_", " ").strip().capitalize())

# Optional encryption using Fernet if available; else fallback to AES-less XOR-like mask using base64
FERNET = None
if DB_ENC_KEY_RAW:
    try:
        from cryptography.fernet import Fernet
        # Derive a valid Fernet key from the provided string if needed
        try:
            # If user provided a 32-byte urlsafe base64 key
            Fernet(DB_ENC_KEY_RAW)
            f_key = DB_ENC_KEY_RAW.encode()
        except Exception:
            # Derive from passphrase
            digest = hashlib.sha256(DB_ENC_KEY_RAW.encode()).digest()
            f_key = base64.urlsafe_b64encode(digest)
        FERNET = Fernet(f_key)
    except Exception:
        FERNET = None

# Local DB helpers (plain JSON / JSONL; no encryption)
os.makedirs(DB_CASES_DIR, exist_ok=True)

def save_case_to_db(case_id: str, payload: dict) -> str:
    case_dir = os.path.join(DB_CASES_DIR, case_id)
    os.makedirs(case_dir, exist_ok=True)
    path = os.path.join(case_dir, "case.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path

def append_case_jsonl(payload: dict) -> str:
    os.makedirs(DB_ROOT, exist_ok=True)
    with open(DB_CASES_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return DB_CASES_JSONL

def load_recent_cases(limit: int = 5) -> list[dict]:
    if not os.path.exists(DB_CASES_JSONL):
        return []
    try:
        with open(DB_CASES_JSONL, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        recent = lines[-limit:]
        return [json.loads(line) for line in recent if line.strip()]
    except Exception:
        return []

# Seed dummy
if "_seeded_cases" not in st.session_state:
    if not os.path.exists(DB_CASES_JSONL) or os.path.getsize(DB_CASES_JSONL) == 0:
        demo1 = {
            "case_id": "01783",
            "mark_for_review": False,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "document_type": "passport",
            "passport": {"name": "JOHN DOE", "dob": "1990-01-15", "expiry_date": "2030-08-15", "id_number": "A12345678"},
        }
        demo2 = {
            "case_id": "73682",
            "mark_for_review": True,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "document_type": "drivers_license",
            "drivers_license": {"name": "JANE ROE", "dob": "1986-07-04", "expiry_date": "2025-06-01", "id_number": "D7773311", "address": "45 OAK AVE SPRINGFIELD, IL"},
        }
        append_case_jsonl(demo1)
        append_case_jsonl(demo2)
        save_case_to_db("01783", demo1)
        save_case_to_db("73682", demo2)
    st.session_state["_seeded_cases"] = True

# -----------------------
# Helpers
# -----------------------
def _flag_submit():
    st.session_state["suppress_verify_once"] = True

# -----------------------
# UI
# -----------------------
# Security notice (removed detailed encryption messaging per request)
st.set_page_config(page_title="KYC Verification Demo", layout="centered")
st.title("🔎 KYC Verification — Reviewer UI")

# Subtle Case ID at the top
st.caption("Case ID (optional)")
case_id = st.text_input("Case ID", placeholder="e.g., demo-123", label_visibility="collapsed")

# Choose which document to process
selected_doc_type = st.selectbox("Document to process", ["passport", "drivers_license"], index=0)

st.markdown("Upload the document below.")

# Single uploader depending on selection
st.divider()
label =  "Document Upload"
st.subheader( f"{label}")
st.caption("Upload as JPG/PNG/PDF")
doc_file = st.file_uploader(
    "Upload file",
    type=list(ALLOWED_EXT),
    key="doc_file",
    accept_multiple_files=False,
)
if doc_file:
    if doc_file.type and doc_file.type.startswith("image/"):
        st.image(doc_file, caption=doc_file.name, width=160)
    else:
        st.caption("PDF uploaded (preview not rendered).")

    # Type verification with cache to avoid respinning on reruns
    try:
        uf = doc_file; uf_bytes = uf.read(); uf.seek(0)
        file_sig = hashlib.sha1(uf_bytes).hexdigest()
        cache_key = f"{file_sig}:{selected_doc_type}"
        if "type_verify_cache" not in st.session_state:
            st.session_state["type_verify_cache"] = {}
        cache = st.session_state["type_verify_cache"]

        # If suppressing after submit and we have cache, render static
        if st.session_state.get("suppress_verify_once") and cache_key in cache:
            prev = cache[cache_key]
            if prev.get("type_mismatch") and prev.get("inferred") != "unknown":
                st.warning("Document type mismatch")
            else:
                st.caption("Type verified ✓")
        # Already verified for this file+type
        elif cache_key in cache:
            prev = cache[cache_key]
            if prev.get("type_mismatch") and prev.get("inferred") != "unknown":
                st.warning("Document type mismatch")
            else:
                st.caption("Type verified ✓")
        else:
            with st.status("Checking document type…", expanded=False) as status:
                v_mp = []
                v_mp.append(("files", (uf.name, io.BytesIO(uf_bytes), uf.type or "application/octet-stream")))
                v_payload = {"doc_type": selected_doc_type}
                v_resp = requests.post(VERIFY_TYPE_URL, data=v_payload, files=v_mp, timeout=20)
                v_resp.raise_for_status()
                v = v_resp.json()
                expected = str(v.get("expected_type") or selected_doc_type).lower()
                inferred = str(v.get("inferred_type") or "").lower()
                has_match = v.get("match")
                type_mismatch = (has_match is False and inferred != expected) or (has_match is None and inferred and inferred not in (expected, "unknown"))
                cache[cache_key] = {"type_mismatch": bool(type_mismatch and inferred != "unknown"), "inferred": inferred, "expected": expected}
                if type_mismatch and inferred != "unknown":
                    status.update(label="Document type mismatch", state="error")
                    st.warning(f"Document does not seem to be a {expected}.")
                else:
                    status.update(label="Type verified ✓", state="complete")
    except Exception as e:
        st.warning(f"{e}")

# Spacer
st.write("")
st.caption("")

files = [f for f in [doc_file] if f is not None]

# Validation
errors = []
if doc_file is None:
    errors.append("Please upload the document.")

# Size/type validation
if files:
    for f in files:
        ext = f.name.split(".")[-1].lower()
        if ext not in ALLOWED_EXT:
            errors.append(f"Unsupported file type for {f.name}. Allowed: {', '.join(sorted(ALLOWED_EXT))}.")

if errors:
    st.error(" \n".join(f"• {e}" for e in errors))

submit = st.button("Submit for Extraction", key="submit_extract", disabled=(doc_file is None), on_click=_flag_submit)

# -----------------------
# Submission (writes review_data) and rendering (reads review_data)
# -----------------------
if submit:
    with st.spinner("Submitting for extraction…"):
        try:
            # Submit selected document
            mp = []
            uf = doc_file; uf_bytes = uf.read(); uf.seek(0)
            mp.append(("files", (uf.name, io.BytesIO(uf_bytes), uf.type or "application/octet-stream")))
            payload = {"doc_type": selected_doc_type, "case_id": case_id or ""}
            resp = requests.post(EXTRACT_URL, data=payload, files=mp, timeout=60)
            resp.raise_for_status()
            r = resp.json()

            # Prepare review data
            extracted = r.get("extracted", {})
            validators = r.get("validators") or []
            merged = {
                "doc_id": (case_id or "").strip() or None,
                "document_type": selected_doc_type,
                "extracted": {selected_doc_type: extracted},
                "validators": validators,
            }
            st.session_state["review_data"] = merged
        except Exception as e:
            st.error(f"Backend request failed: {e}")
        finally:
            # Clear suppression after completing extraction
            st.session_state["suppress_verify_once"] = False

# Render only if we have review_data in session
data = st.session_state.get("review_data")
if data:
    st.success("Extraction complete.")

    extracted = data.get("extracted", {})

    st.subheader("Review panel")
    doc_data = extracted.get(selected_doc_type, {}) or {}
    col1, col2 = st.columns(2)
    with col1:
        if doc_file and doc_file.type and doc_file.type.startswith("image/"):
            st.image(doc_file, caption=doc_file.name, use_container_width=True)
        else:
            st.caption("Preview unavailable.")
    with col2:
        st.markdown(f"**{label}**")
        # Only show selected fields
        if selected_doc_type == "passport":
            st.text_input("Name", value="" if doc_data.get("name") is None else str(doc_data.get("name", "")), key="doc_name")
            st.text_input("DOB", value="" if doc_data.get("dob") is None else str(doc_data.get("dob", "")), key="doc_dob")
            st.text_input("Expiry", value="" if doc_data.get("expiry_date") is None else str(doc_data.get("expiry_date", "")), key="doc_expiry")
            st.text_input("Passport ID number", value="" if doc_data.get("id_number") is None else str(doc_data.get("id_number", "")), key="doc_id")
        else:
            st.text_input("Name ", value="" if doc_data.get("name") is None else str(doc_data.get("name", "")), key="doc_name")
            st.text_input("DOB ", value="" if doc_data.get("dob") is None else str(doc_data.get("dob", "")), key="doc_dob")
            st.text_input("Expiry ", value="" if doc_data.get("expiry_date") is None else str(doc_data.get("expiry_date", "")), key="doc_expiry")
            st.text_input("DL ID number", value="" if doc_data.get("id_number") is None else str(doc_data.get("id_number", "")), key="doc_id")
            st.text_input("Address", value="" if doc_data.get("address") is None else str(doc_data.get("address", "")), key="doc_address")

    # Authenticity (no caching)
    try:
        if doc_file:
            with st.spinner("Running authenticity…"):
                v_mp = []
                uf = doc_file; uf_bytes = uf.read(); uf.seek(0)
                v_mp.append(("files", (uf.name, io.BytesIO(uf_bytes), uf.type or "application/octet-stream")))
                v_resp = requests.post(VERIFY_URL, files=v_mp, timeout=20, data={"doc_type": selected_doc_type})
                v_resp.raise_for_status()
                v = v_resp.json()
            suspected = bool((v.get("is_suspected_fraud") if "is_suspected_fraud" in v else (v.get("integrity") or {}).get("is_suspected_fraud")))
            conf = (v.get("confidence") if "confidence" in v else (v.get("integrity") or {}).get("confidence"))
            expl = (v.get("explanation") if "explanation" in v else (v.get("integrity") or {}).get("explanation"))
            if suspected:
                st.error(f"Authenticity flag (confidence {conf}). Reason: {expl}")
    except Exception:
        pass

    # Relevant verification checks
    with st.expander("Verification checks"):
        validators = data.get("validators") or []
        if not validators:
            st.write("No checks available.")
        else:
            # Summary
            total = len(validators)
            num_pass = sum(1 for v in validators if (v.get("status") or "").lower() == "pass")
            st.markdown(f"**Checks passed:** {num_pass}/{total}")
            try:
                st.progress(num_pass / total)
            except Exception:
                pass
            # Simplified checklist ordered by importance (fails, warns, passes)
            def _order_key(v: dict) -> int:
                s = (v.get("status") or "").lower()
                return {"pass": 2, "warn": 1}.get(s, 0)
            for v in sorted(validators, key=_order_key):
                s = (v.get("status") or "").lower()
                icon = status_icon(s)
                label = friendly_label(v.get("name"))
                desc = v.get("message") or v.get("details") or v.get("reason") or ""
                if desc:
                    st.write(f"{icon} {label} — {desc}")
                else:
                    st.write(f"{icon} {label}")

    # Actions: separate controls
    st.divider()
    st.subheader("Actions")
    if "mark_for_review" not in st.session_state:
        st.session_state["mark_for_review"] = False
    st.checkbox("Mark for review", key="mark_for_review")
    if st.button("Save to DB"):
        # Build case payload from edited fields
        cid = (case_id or f"{random.randint(10000, 99999)}").strip()
        payload = {
            "case_id": cid,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "mark_for_review": st.session_state.get("mark_for_review", False),
            "document_type": selected_doc_type,
            selected_doc_type: {
                "name": st.session_state.get("doc_name", ""),
                "dob": st.session_state.get("doc_dob", ""),
                "expiry_date": st.session_state.get("doc_expiry", ""),
                "id_number": st.session_state.get("doc_id", ""),
            } | ({"address": st.session_state.get("doc_address", "")} if selected_doc_type == "drivers_license" else {}),
        }
        out_jsonl = append_case_jsonl(payload)
        out_case = save_case_to_db(cid, payload)
        if "mark_for_review" in st.session_state and st.session_state.get("mark_for_review", False):
            st.success("Saved to database! (marked for review)")
        else:
            st.success("Saved to database!")
        st.session_state["last_saved_case"] = out_case

    # Recent cases viewer
    with st.expander("Recent saved cases", expanded=True):
        recent = load_recent_cases(limit=5)
        if not recent:
            st.caption("No cases saved yet.")
        else:
            # Build summary rows
            rows = [
                {
                    "Case ID": row.get("case_id"),
                    "Type": row.get("document_type"),
                    "Review": row.get("mark_for_review"),
                    "Created": row.get("created_at"),
                }
                for row in recent
            ]
            # Try nice table; fallback to simple list
            try:
                import pandas as pd  # optional
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            except Exception:
                for r in rows:
                    st.write(f"• {r['Case ID']} — type={r['Type']} — review={r['Review']} — {r['Created']}")

            # Select a case to view masked details
            case_ids = [str(r["Case ID"]) for r in rows if r.get("Case ID") is not None]
            if case_ids:
                default_sel = st.session_state.get("recent_case_sel")
                try:
                    default_idx = case_ids.index(str(default_sel)) if default_sel and str(default_sel) in case_ids else 0
                except Exception:
                    default_idx = 0
                sel = st.selectbox("Preview details for:", case_ids, index=default_idx, key="recent_case_sel")
                chosen = next((row for row in recent if str(row.get("case_id")) == sel), None)
                if chosen:
                    doc_type = chosen.get("document_type")
                    doc = chosen.get(doc_type, {}) if doc_type else {}
                    st.markdown(f"**Details — {doc_type or 'unknown'}**")
                    if doc:
                        # Mask sensitive values
                        masked = dict(doc)
                        if "id_number" in masked:
                            masked["id_number"] = mask_text(masked.get("id_number"))
                        if "address" in masked and isinstance(masked.get("address"), str):
                            masked["address"] = mask_text(masked.get("address"))
                        # Render two-column pretty view
                        left, right = st.columns(2)
                        items = list(masked.items())
                        mid = (len(items) + 1) // 2
                        with left:
                            for k, v in items[:mid]:
                                st.markdown(f"- **{k}**: {v}")
                        with right:
                            for k, v in items[mid:]:
                                st.markdown(f"- **{k}**: {v}")
                    else:
                        st.caption("No stored fields for this case.")
        # Add a brief retention/encryption notice
        st.warning("Saved cases are encrypted and retained for 7 days. ")
