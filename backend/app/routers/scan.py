import json
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

router    = APIRouter(prefix="/scan", tags=["Scan"])
templates = Jinja2Templates(directory="app/templates")

# ── SCAN PAGE ─────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def scan_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="scan/index.html", context={}
    )

# ── EXTRACT — receives image, calls Gemini Vision, returns structured JSON ────

@router.post("/extract")
async def extract_bill(request: Request):
    data = await request.json()

    image_b64  = data.get("image")
    media_type = data.get("media_type", "image/jpeg")

    if not image_b64:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "No image provided"}
        )

    prompt = """You are an expert data extraction AI. Read this handwritten Indian jewellery shop tax invoice and extract the data into a strict JSON structure. 

Return ONLY a valid JSON object. Do not include markdown formatting, code blocks, or explanations.

Return this EXACT structure. Extract the ACTUAL numbers from the bill. ONLY use 0.0 if the field is completely blank or missing:
{
  "invoice_date": "YYYY-MM-DD", 
  "invoice_type": "sale", 
  "party_name": "customer name or null",
  "party_phone": "phone digits only or null",
  "party_address": "address or null",
  "party_gstin": "GSTIN or null",
  "payment_mode": "cash", 
  "items": [
    {
      "item_name": "description of item",
      "purity": "22K or null",
      "weight_grams": <actual number from bill, or 0.0 if blank>,
      "rate_per_gram": <actual number from bill, or 0.0 if blank>,
      "making_charges": <actual number from bill, or 0.0 if blank>,
      "hsn_code": "7113 or null",
      "amount": <actual number from bill, or 0.0 if blank>
    }
  ],
  "old_gold_value": <actual number from bill, or 0.0 if blank>,
  "discount": <actual number from bill, or 0.0 if blank>,
  "grand_total": <actual number from bill, or 0.0 if blank>,
  "amount_paid": <actual number from bill, or 0.0 if blank>,
  "notes": "handwritten remarks only or null"
}

CRITICAL DATA TYPE RULES (FAILURE IS NOT AN OPTION):
1. DATES: `invoice_date` MUST be strictly in ISO 8601 format: YYYY-MM-DD. If you cannot read the date, return the current date. Do not use DD-MM-YYYY.
2. NUMBERS: For all numeric fields marked with <>, extract the real value from the bill. They MUST be output as pure floats or integers (e.g., 5500.50 or 0). 
   - NEVER put numbers in quotes. 
   - NEVER include commas, 'Rs', '₹', or 'g'. 
3. STRINGS: If a text field (name, address) is missing, return null (lowercase, unquoted).
4. PAYMENT & TYPE: `payment_mode` should default to "cash" if unseen. `invoice_type` should default to "sale".

EXTRACTION LOGIC:
- "Particulars" -> `item_name`.
- "Qty." -> `weight_grams` (unless it says 'pcs').
- Old Gold/Jama/Return -> put the value as a positive float in `old_gold_value`.
- Discount/Less -> put the value as a positive float in `discount`.
- DO NOT extract printed boilerplate text (Terms, Bank Details, Signatory) into the `notes` field. Only handwritten notes.
"""

    raw = ""
    try:
        import base64
        from google import genai
        from google.genai import types
        from app.config import settings

        if not settings.GOOGLE_API_KEY:
            return JSONResponse(
                status_code=503,
                content={"success": False, "error": "Google API key not configured"},
            )

        client = genai.Client(api_key=settings.GOOGLE_API_KEY)

        image_bytes = base64.b64decode(image_b64)

        fallback_models = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-2.0-flash-001",
            "gemini-2.0-flash-lite-001",
            "gemini-2.0-flash-lite",
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
            "gemini-2.5-flash-lite",
            ]

        for model_name in fallback_models:
            try:
                response = client.models.generate_content(
                    model    = model_name,
                    contents = [
                        types.Part.from_bytes(
                            data      = image_bytes,
                            mime_type = media_type,
                        ),
                        prompt,
                    ],
                )

                raw = response.text.strip()
                break
            except Exception as e:
                error_msg = str(e)
                
                if ("503" in error_msg or "429" in error_msg) and model_name != fallback_models[-1]:
                    print(f"⚠️ {model_name} is busy. Falling back to the next model...")
                    continue 
                else:
                    raise e

        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        extracted = json.loads(raw)
        return {"success": True, "data": extracted}

    except json.JSONDecodeError as e:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error":   f"Could not parse Gemini response as JSON: {str(e)}",
                "raw":     raw,
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )