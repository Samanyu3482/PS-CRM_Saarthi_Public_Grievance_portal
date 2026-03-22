import google.generativeai as genai
from app.core.config import settings
import logging

if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

async def check_duplicate_complaint(new_desc: str, existing_descs: list[str]) -> bool:
    """
    Checks if a new complaint description mathematically/semantically matches 
    any existing complaints previously submitted by the same user.
    """
    if not settings.GEMINI_API_KEY or not existing_descs:
        return False
        
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            "You are a deduplication assistant for a public service CRM.\n"
            "A citizen is submitting a new complaint. Below is the description of the NEW complaint:\n"
            f"---NEW COMPLAINT---\n{new_desc}\n------------------\n\n"
            "Below is a list of their PREVIOUSLY SUBMITTED complaints:\n"
        )
        for i, desc in enumerate(existing_descs):
            prompt += f"{i+1}. {desc}\n"
            
        prompt += (
            "\nAnalyze if the NEW complaint is referring to the EXACT SAME specific issue/incident as any of the PREVIOUS complaints. "
            "Reply with exactly 'YES' if it is a duplicate, or exactly 'NO' if it is a newly reported issue. Do not include any other text."
        )
        
        response = await model.generate_content_async(prompt)
        text = response.text.strip().upper()
        return "YES" in text
    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
        return False  # Fail open so the user isn't blocked if AI fails
