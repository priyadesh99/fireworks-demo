# fireworks-demo


## Repository structure

```
firewoks_demo/
 ├─ takehome/
 │   ├─ backend/
 │   │   ├─ main.py                # FastAPI app and endpoints
 │   │   ├─ extract.py             # Fireworks LLM extraction helpers
 │   │   ├─ validators.py          # Rule-based checks + consistency
 │   │   └─ verify.py              # Doc type + authenticity checks
 │   └─ frontend/
 │       └─ app.py                 # Streamlit reviewer UI
 └─ local_db/                      # Created at runtime; JSON/JSONL demo store
```

Example installation:
```bash
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn python-multipart pydantic streamlit requests python-dotenv fireworks pandas
```
## Environment variables

- `FIREWORKS_API_KEY` (required by backend)
- `BACKEND_URL` (optional for frontend; defaults to `https://fireworks-demo-kyc.onrender.com` in the demo. Set to your local backend during dev.)
---

## Running locally

1) Start the backend (FastAPI):
```bash
# From repo root
source .venv/bin/activate
uvicorn takehome.backend.main:app --reload --port 8000
```

2) Start the frontend (Streamlit):
```bash
# New terminal, same repo root
source .venv/bin/activate
export BACKEND_URL=http://127.0.0.1:8000
streamlit run takehome/frontend/app.py

Open the Streamlit URL shown in the terminal (usually `http://localhost:8501`).


## Backend API

### /health (GET)
- Returns `{ "status": "ok" }`

### /verify_type (POST)
- Purpose: Verify the uploaded document looks like the expected type
- Input: multipart/form-data
  - `files`: file[] (1 file)
  - `doc_type`: `passport` | `drivers_license`
- Output (example):
```json
{
  "expected_type": "passport",
  "inferred_type": "passport",
  "match": true
}
```
## Architecture

- **Frontend**: `Streamlit` app at `takehome/frontend/app.py`
  - Uploads the document
  - Calls backend `/verify_type` on upload
  - Calls backend `/extract` on submit
  - Runs `/verify` during review to flag authenticity only on suspicion
  - Renders extracted fields, checks, and actions to save

- **Backend**: `FastAPI` app at `takehome/backend/main.py`
  - `/health`: health check
  - `/verify_type`: light-weight doc-type inference
  - `/verify`: authenticity/integrity heuristic via LLM
  - `/extract`: structured extraction via LLM + rule validators

- **LLM integration**: `takehome/backend/extract.py`, `takehome/backend/verify.py`
  - Uses Fireworks `LLM(model="llama4-maverick-instruct-basic", deployment_type="auto")`
  - Vision chat with base64 data URL payloads
  - Prompts return strictly JSON; backend hardens parsing

- **Validation**: `takehome/backend/validators.py`
  - Required fields per doc type
  - Age ≥ 18
  - Expiry date validity
  - Cross-doc consistency (rule-first + optional LLM fallback)

- **Persistence**: local files under `local_db/`
  - JSONL index: `local_db/cases.jsonl`
  - Per-case JSON: `local_db/cases/<CASE_ID>/case.json`

    
### /verify (POST)
- Purpose: Authenticity/integrity heuristic (show a flag only if suspicious)
- Input: multipart/form-data
  - `files`: file[] (1 file)
  - `doc_type`: `passport` | `drivers_license`
  - `case_id`: optional
- Output (example):
```json
{
  "doc_type": "drivers_license",
  "integrity": {
    "is_suspected_fraud": true,
    "confidence": 0.9,
    "explanation": "The driver's license has 'SAMPLE' written on it."
  }
}
```

### /extract (POST)
- Purpose: Extract key fields and run rule validators
- Input: multipart/form-data
  - `files`: file[] (1 file)
  - `doc_type`: `passport` | `drivers_license`
  - `case_id`: optional
- Output (example for passport):
```json
{
  "doc_id": "demo-doc",
  "doc_type": "passport",
  "model": "llama4-maverick-instruct-basic",
  "extracted": {
    "name": "JANE DOE",
    "dob": "1995-12-01",
    "issuing_country": "USA",
    "id_number": "A1234567",
    "expiry_date": "2030-07-22"
  },
  "validators": [
    {"name": "validate_required_fields_passport", "status": "pass"},
    {"name": "age_check", "status": "pass"},
    {"name": "expiry_check", "status": "pass"}
  ],
  "score": 0,
  "final_status": "pass"
}
```

Curl examples:
```bash
# Health
curl -s http://127.0.0.1:8000/health

# Verify type
curl -s -X POST http://127.0.0.1:8000/verify_type \
  -F doc_type=passport \
  -F files=@/path/to/passport.jpg

# Authenticity
curl -s -X POST http://127.0.0.1:8000/verify \
  -F doc_type=drivers_license \
  -F files=@/path/to/dl.jpg

# Extract
curl -s -X POST http://127.0.0.1:8000/extract \
  -F doc_type=passport \
  -F case_id=demo-123 \
  -F files=@/path/to/passport.jpg
```

---

## Extending the PoC

- Add new validators in `validators.py` and include them in `/extract` responses
- Support additional ID types by creating new extraction prompts and validators
- Swap LLM models or add deterministic OCR pre-processing before LLM extraction
- Replace local JSON/JSONL with a proper database and add server-side authn/authz
- Record audit events (timestamps, user IDs) and version edits
