# takehome/backend/main.py
import fastapi
from fastapi import UploadFile, File, Form
from pydantic import BaseModel
from extract import FireworksLLM
from fastapi.middleware.cors import CORSMiddleware
from validators import (
    validate_required_fields_passport,
    validate_required_fields_drivers_license,
    validate_consistency_passport_and_drivers_license,
)
from verify import verify_document_integrity, verify_document_type
import json

app = fastapi.FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # or your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fireworks_llm = FireworksLLM()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/verify_type")
async def verify_type(files: list[UploadFile] = File(...),
                      doc_type: str = Form(...)):
    uf = files[0]
    file_bytes = await uf.read()
    result = verify_document_type(file_bytes, uf.content_type or "image/jpeg", doc_type)
    return result if isinstance(result, dict) else {}

@app.post("/verify")
async def verify(files: list[UploadFile] = File(...), doc_type: str = Form(...)):
    uf = files[0]
    file_bytes = await uf.read()
    result = verify_document_integrity(file_bytes, uf.content_type or "image/jpeg", doc_type)
    print(result)
    return result if isinstance(result, dict) else {}

@app.post("/extract")
async def extract(files: list[UploadFile] = File(...),
                  doc_type: str = Form(...),
                  case_id: str = Form("")):
    uf = files[0]
    file_bytes = await uf.read()
    if doc_type == "passport":
        extracted = fireworks_llm.extract_passport(file_bytes, uf.content_type or "image/jpeg")
        validators = validate_required_fields_passport(extracted)
    else:
        extracted = fireworks_llm.extract_drivers_license(file_bytes, uf.content_type or "image/jpeg")
        validators = validate_required_fields_drivers_license(extracted)

    final_status = "pass" if all(v.get("status") == "pass" for v in validators) else "fail"

    return {
        "doc_id": case_id or "demo-doc",
        "doc_type": doc_type,
        "model": "llama4-maverick-instruct-basic",
        "extracted": extracted,
        "validators": validators,
        "score": 0,
        "final_status": final_status,
    }

@app.post("/extract/both")
async def extract_both(passport: UploadFile = File(...),
                       drivers_license: UploadFile = File(...),
                       case_id: str = Form("")):
    # Read files
    p_bytes = await passport.read()
    d_bytes = await drivers_license.read()

    # Extract
    p_extracted = fireworks_llm.extract_passport(p_bytes, passport.content_type or "image/jpeg")
    d_extracted = fireworks_llm.extract_drivers_license(d_bytes, drivers_license.content_type or "image/jpeg")

    # Validate
    p_validators = validate_required_fields_passport(p_extracted)
    d_validators = validate_required_fields_drivers_license(d_extracted)
    consistency = validate_consistency_passport_and_drivers_license(p_extracted, d_extracted)
    validators = p_validators + d_validators + consistency

    final_status = "pass" if all(v.get("status") == "pass" for v in validators) else "fail"

    return {
        "doc_id": case_id or "demo-doc",
        "doc_type": "both",
        "model": "llama4-maverick-instruct-basic",
        "extracted": {
            "passport": p_extracted,
            "drivers_license": d_extracted,
        },
        "validators": validators,
        "score": 0,
        "final_status": final_status,
    }