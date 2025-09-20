from fireworks import LLM
from dotenv import load_dotenv
import os, base64, json, re

load_dotenv()
api_key = os.getenv("FIREWORKS_API_KEY")
if not api_key:
    raise ValueError("FIREWORKS_API_KEY not set in environment")

class FireworksLLM:
    def __init__(self):
        self.llm = LLM(model="llama4-maverick-instruct-basic",
                       deployment_type="auto",
                       api_key=api_key)
        self.ocr = LLM(model = "accounts/fireworks/models/firesearch-ocr-v6",
                       id="accounts/priya1605/deployments/ik5cfzil",
                       deployment_type="on-demand",
                       api_key=api_key)

    def extract_passport(self, file_bytes: bytes, mime: str):
        prompt = """Extract the following fields from this Passport.
                Return only JSON with keys: name, dob (YYYY-MM-DD), issuing_country (ISO3),
                id_number, expiry_date (YYYY-MM-DD).
                If a field is missing, set it to null.
                Ensure the output is only a valid JSON object."""
        
        return self.extract_bytes(prompt, file_bytes, mime)
    
    def extract_drivers_license(self, file_bytes: bytes, mime: str):
        prompt = """Extract the following fields from this ID document.
                Return only JSON with keys: name, dob (YYYY-MM-DD), issuing_state (USPS),
                id_number, expiry_date (YYYY-MM-DD), address.
                If a field is missing, set it to null.
                Ensure the output is only a valid JSON object."""
        
        return self.extract_bytes(prompt, file_bytes, mime)
    
    def extract_bytes(self, prompt: str, file_bytes: bytes, mime: str):
        b64 = base64.b64encode(file_bytes).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"
        resp = self.llm.chat.completions.create(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }]
        )
        text = resp.choices[0].message.content
        try:
            text = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", text.strip(), flags=re.MULTILINE)
            print(text)
            return json.loads(text) if isinstance(text, str) else (text or {})
        except Exception:
            return {}
        
    def extract_via_ocr(self, prompt: str, file_bytes: bytes, mime: str):
        raw_text = self.ocr_text(file_bytes, mime)
        parsing_prompt = (
            f"{prompt}\n\nOCR_TEXT:\n" + raw_text[:12000]
        )
        return self.extract_bytes(parsing_prompt, file_bytes, mime)
    
    def ocr_text(self, file_bytes: bytes, mime: str):
        b64 = base64.b64encode(file_bytes).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"
        resp = self.ocr.chat.completions.create(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": "Transcribe all legible text exactly as seen (no summaries)."},
                ],
            }]
        )
        return resp.choices[0].message.content or ""