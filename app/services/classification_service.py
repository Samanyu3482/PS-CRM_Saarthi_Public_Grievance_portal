import asyncio
import os
import json
import logging
import re
from google import generativeai as genai
from app.schemas.complaint import ComplaintInDB

# ── Gemini setup ─────────────────────────────────────────────────────────────
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
_model = genai.GenerativeModel("gemini-3-flash")

# ── Prompt ────────────────────────────────────────────────────────────────────
_PROMPT_TEMPLATE = """
You are an AI system that classifies Indian public grievances for the CPGRAMS system.
Classify into Ministry, Department, and Sub-unit.

Return STRICT JSON only — no explanation, no markdown, no code fences:
{{
  "ministry": "...",
  "department": "...",
  "sub_department": "..."
}}

If unsure about any field, use "UNKNOWN".

----------------------------------------
MINISTRY & DEPARTMENT STRUCTURE:

Ministry of Finance:
  - Department of Revenue → Income Tax Department, CBIC (Customs & GST)
  - Department of Financial Services → Public Sector Banks, Insurance Companies, PFRDA (Pension)

Ministry of Railways:
  - Railway Board → Ticket Booking Issues, Refund Issues, Passenger Complaints

Ministry of Petroleum and Natural Gas:
  - Oil Marketing Companies → LPG Subsidy, Gas Delivery, Fuel Quality

Ministry of Labour and Employment:
  - EPFO → PF Withdrawal, PF Transfer, UAN Issues
  - ESIC → ESI Claims, Hospital Services

Ministry of Housing and Urban Affairs:
  - Urban Bodies → CPWD, DDA, Municipal Services

Ministry of Power:
  - Electricity Services → Power Cuts, Billing Issues

Ministry of Communications:
  - Telecom → Call Drops, Network Issues
  - Postal Services → Speed Post Delay, Parcel Issues

Ministry of Health and Family Welfare:
  - Health Services → Hospital Complaints, Medicine Availability, CGHS Issues

Ministry of Education:
  - School Education → Mid-Day Meal, Scholarship Issues
  - Higher Education → University Grants, Examination Issues

Ministry of Agriculture:
  - Farmers Welfare → PM-KISAN Issues, Crop Insurance, Fertilizer Supply
----------------------------------------

Complaint:
"{user_input}"
"""

# ── Fallback keyword map (used if Gemini fails or returns UNKNOWN) ────────────
_KEYWORD_FALLBACK: list[tuple[re.Pattern, dict]] = [
    (re.compile(r"\b(train|railway|irctc|ticket|refund|berth|platform)\b", re.IGNORECASE), {
        "ministry": "Ministry of Railways",
        "department": "Railway Board",
        "sub_department": "Passenger Complaints",
    }),
    (re.compile(r"\b(lpg|gas cylinder|petrol|diesel|fuel|subsidy)\b", re.IGNORECASE), {
        "ministry": "Ministry of Petroleum and Natural Gas",
        "department": "Oil Marketing Companies",
        "sub_department": "LPG Subsidy",
    }),
    (re.compile(r"\b(pf|provident fund|epfo|uan|esic|esi)\b", re.IGNORECASE), {
        "ministry": "Ministry of Labour and Employment",
        "department": "EPFO",
        "sub_department": "PF Withdrawal",
    }),
    (re.compile(r"\b(electricity|power cut|billing|meter|light)\b", re.IGNORECASE), {
        "ministry": "Ministry of Power",
        "department": "Electricity Services",
        "sub_department": "Billing Issues",
    }),
    (re.compile(r"\b(income tax|gst|customs|cbic|pan card|tax refund)\b", re.IGNORECASE), {
        "ministry": "Ministry of Finance",
        "department": "Department of Revenue",
        "sub_department": "Income Tax Department",
    }),
    (re.compile(r"\b(hospital|medicine|cghs|doctor|health|ambulance)\b", re.IGNORECASE), {
        "ministry": "Ministry of Health and Family Welfare",
        "department": "Health Services",
        "sub_department": "Hospital Complaints",
    }),
    (re.compile(r"\b(speed post|parcel|courier|postal|post office)\b", re.IGNORECASE), {
        "ministry": "Ministry of Communications",
        "department": "Postal Services",
        "sub_department": "Speed Post Delay",
    }),
    (re.compile(r"\b(network|call drop|sim|jio|airtel|bsnl|telecom)\b", re.IGNORECASE), {
        "ministry": "Ministry of Communications",
        "department": "Telecom",
        "sub_department": "Network Issues",
    }),
    (re.compile(r"\b(scholarship|school|mid.?day meal|university|exam|ugc)\b", re.IGNORECASE), {
        "ministry": "Ministry of Education",
        "department": "School Education",
        "sub_department": "Scholarship Issues",
    }),
    (re.compile(r"\b(kisan|farmer|crop|fertilizer|kcc|agriculture)\b", re.IGNORECASE), {
        "ministry": "Ministry of Agriculture",
        "department": "Farmers Welfare",
        "sub_department": "PM-KISAN Issues",
    }),
]

_UNKNOWN_RESULT = {
    "ministry": "UNKNOWN",
    "department": "UNKNOWN",
    "sub_department": "UNKNOWN",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_gemini_response(raw: str) -> dict | None:
    """
    Safely extract JSON from Gemini output.
    Handles cases where the model wraps output in ```json ... ``` fences.
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try extracting the first {...} block
        match = re.search(r"\{.*?\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def _keyword_fallback(text: str) -> dict | None:
    """Return first keyword-matched department, or None if no match."""
    for pattern, result in _KEYWORD_FALLBACK:
        if pattern.search(text):
            return result
    return None


def _is_fully_classified(result: dict) -> bool:
    """True only if all three fields are non-empty and not UNKNOWN."""
    return all(
        result.get(k) and result[k] != "UNKNOWN"
        for k in ("ministry", "department", "sub_department")
    )


# ── Main classification function ──────────────────────────────────────────────

async def classify_complaint(title: str, description: str) -> dict:
    """
    Classify a complaint into ministry / department / sub_department.

    Strategy:
      1. Call Gemini with full prompt
      2. If Gemini returns valid JSON with no UNKNOWNs → use it
      3. If partial/failed → fill missing fields via keyword fallback
      4. If both fail → return UNKNOWN across all fields

    Returns
    -------
    dict with keys: ministry, department, sub_department, source
        source: "gemini" | "fallback" | "unknown"
    """
    combined_text = f"{title}. {description}"
    result = None

    # ── Step 1: Gemini ────────────────────────────────────────────────────────
    try:
        prompt = _PROMPT_TEMPLATE.format(user_input=combined_text)
        response = await asyncio.to_thread(_model.generate_content, prompt)
        raw = response.text.strip()
        parsed = _parse_gemini_response(raw)

        if parsed:
            # Normalise key — your schema uses sub_department, prompt uses sub_unit
            if "sub_unit" in parsed and "sub_department" not in parsed:
                parsed["sub_department"] = parsed.pop("sub_unit")
            result = parsed

    except Exception as e:
        logging.warning(f"[classification_service] Gemini call failed: {e}")

    # ── Step 2: Keyword fallback (full or partial fill) ───────────────────────
    if not result or not _is_fully_classified(result):
        fallback = _keyword_fallback(combined_text)
        if fallback:
            if not result:
                result = {**_UNKNOWN_RESULT, **fallback, "source": "fallback"}
            else:
                # Fill only the UNKNOWN fields from fallback
                for key in ("ministry", "department", "sub_department"):
                    if not result.get(key) or result[key] == "UNKNOWN":
                        result[key] = fallback.get(key, "UNKNOWN")
                result["source"] = "gemini+fallback"
        else:
            result = {**_UNKNOWN_RESULT, "source": "unknown"} if not result else {
                **result, "source": "unknown"
            }
    else:
        result["source"] = "gemini"

    logging.info(
        f"[classification_service] title='{title[:40]}' → "
        f"{result.get('ministry')} / {result.get('department')} / "
        f"{result.get('sub_department')} (source={result.get('source')})"
    )

    return result


# ── Reclassify an existing complaint (called from complaint_service) ──────────

async def reclassify_complaint(complaint: ComplaintInDB) -> dict:
    """
    Re-run classification on an already-stored complaint.
    Useful for admin-triggered re-routing or batch correction jobs.
    """
    return await classify_complaint(complaint.title, complaint.description)