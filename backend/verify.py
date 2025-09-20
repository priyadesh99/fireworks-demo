from dotenv import load_dotenv
import os, re
from extract import FireworksLLM

load_dotenv()
api_key = os.getenv("FIREWORKS_API_KEY")
if not api_key:
    raise ValueError("FIREWORKS_API_KEY not set in environment")

fireworks_llm = FireworksLLM()


def verify_document_type(file_bytes: bytes, mime: str, doc_type: str):
    inferred_type = "unknown"

    ocr_text = fireworks_llm.ocr_text(file_bytes, mime)
    raw_text_upper = ocr_text.upper()

    if "PASSPORT" in raw_text_upper:  # MRZ line indicator
        inferred_type = "passport"
    elif "DRIVER" in raw_text_upper or "DL" in raw_text_upper or "DRIVER LICENSE" in raw_text_upper:
        inferred_type = "drivers_license"


    match = (inferred_type == doc_type)

    return {
        "expected_type": doc_type,
        "inferred_type": inferred_type,
        "match": match,
    }

    
        # check whether ocr text contains pass

def verify_document_integrity(file_bytes: bytes, mime: str, doc_type: str):
    if doc_type == "passport":
        prompt = """You are a cautious identity verification assistant. 
                You are shown an image of a passport
                Your task is to assess whether the document appears authentic or suspicious.

                Return ONLY JSON with the following fields:
                {
                "is_suspected_fraud": true | false,
                "confidence": 0.0–1.0,
                "explanation": "short rationale"
                }
                If the document is not a passport, return "is_suspected_fraud": true with high confidence and explain.


                    Guidelines:
                - Look for tampering: mismatched fonts, cut-and-paste artifacts, blurred text, misaligned photo, missing hologram/barcode/MRZ.
                - Look for validity: presence of MRZ lines (passport) consistent fonts, correct placement of fields.
                - If uncertain, return "is_suspected_fraud": false with low confidence and explain.
                - Do not hallucinate security features that are not visible."""
        
    elif doc_type == "drivers_license":
        prompt = """You are a cautious identity verification assistant. 
                You are shown an image of a driver's license
                Your task is to assess whether the document appears authentic or suspicious.

                Return ONLY JSON with the following fields:
                {
                "is_suspected_fraud": true | false,
                "confidence": 0.0–1.0,
                "explanation": "short rationale"
                } 
                If the document is not a driver's license, return "is_suspected_fraud": true with high confidence and explain.
                    Guidelines:
                - Look for tampering: mismatched fonts, cut-and-paste artifacts, blurred text, misaligned photo, missing hologram/barcode/MRZ.
                - Look for validity: presence of PDF417 barcode (DL), consistent fonts, correct placement of fields.
                - If uncertain, return "is_suspected_fraud": false with low confidence and explain.
                - Do not hallucinate security features that are not visible."""
                

    result = fireworks_llm.extract_bytes(prompt, file_bytes, mime)              
    return result
