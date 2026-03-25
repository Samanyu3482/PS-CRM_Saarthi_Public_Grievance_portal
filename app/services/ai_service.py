import logging
import math
import re
import numpy as np
from datetime import datetime, timezone
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

_model = SentenceTransformer('all-MiniLM-L6-v2')

COSINE_THRESHOLD = 0.8
DISTANCE_THRESHOLD_M = 20
TIME_THRESHOLD_H = 24

# ---------- Spam / Abuse config ----------
SPAM_STATUS = "flagged_spam"          # stored as complaint status
SPAM_PRIORITY = "low"                 # de-prioritised for officer review

BLACKLISTED_PATTERNS: list[re.Pattern] = [pattern for pattern in [
    # Abusive / hate
    re.compile(r"\b(bastard|bh?ench?od|ch?utiya|madarch?od|gaandu|saala|sala|haramzada|harami|randi|mc\b|bc\b)\b", re.IGNORECASE),
    # Explicit sexual
    re.compile(r"\b(sex|porn|nude|naked|xxx)\b", re.IGNORECASE),
    # Threats / violence
    re.compile(r"\b(kill|murder|bomb|blast|terrorist|jihad|shoot)\b", re.IGNORECASE),
    # Nonsense / test submissions
    re.compile(r"\b(test|testing|dummy|fake|asdf|qwerty|lorem ipsum|hello world|abcd)\b", re.IGNORECASE),
    # Spam-y commercial patterns
    re.compile(r"(buy now|click here|free offer|win prize|congratulations you (have|'ve) won)", re.IGNORECASE),
] if pattern]


def check_spam(title: str, description: str) -> dict:
    """
    Scan title + description against blacklisted keyword patterns.

    Returns
    -------
    dict with keys:
        is_spam      : bool
        matched_on   : list[str]  – which patterns triggered
        reason       : str        – human-readable summary for officer
    """
    combined = f"{title} {description}"
    matched_on: list[str] = []

    for pattern in BLACKLISTED_PATTERNS:
        hits = pattern.findall(combined)
        if hits:
            # Deduplicate matched words, lowercase
            matched_on.extend({h.lower() if isinstance(h, str) else h[0].lower() for h in hits})

    if matched_on:
        return {
            "is_spam": True,
            "matched_on": list(set(matched_on)),
            "reason": f"Flagged for review — matched keywords: {', '.join(set(matched_on))}",
        }

    return {"is_spam": False, "matched_on": [], "reason": ""}


def get_embedding(text: str) -> np.ndarray:
    """Return a 384-dim embedding vector for the given text."""
    return _model.encode(text)


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def check_duplicate_complaint(
    new_embedding: np.ndarray,        # ✅ accepts pre-computed vector
    new_lat: float | None,
    new_lng: float | None,
    new_time: datetime,
    existing_complaints: list[dict],
) -> dict | None:
    if not existing_complaints:
        return {"is_duplicate": False, "duplicate_of": None}

    try:
        new_emb = np.array(new_embedding).reshape(1, -1)  # ✅ no re-encoding

        for comp in existing_complaints:
            # --- 1. Cosine similarity ---
            stored_emb = comp.get("embedding")
            if stored_emb is not None:
                comp_emb = np.array(stored_emb).reshape(1, -1)
            else:
                comp_emb = get_embedding(comp.get("description", "")).reshape(1, -1)

            sim = cosine_similarity(new_emb, comp_emb)[0][0]
            if sim < COSINE_THRESHOLD:
                continue

            # --- 2. Geo distance ---
            coords = (comp.get("location") or {}).get("coordinates") or {}
            comp_lat = coords.get("lat")
            comp_lng = coords.get("lng")

            # ✅ if either side missing coords, skip — can't confirm same location
            if new_lat is None or new_lng is None or comp_lat is None or comp_lng is None:
                continue

            dist = haversine_distance(new_lat, new_lng, comp_lat, comp_lng)
            if dist > DISTANCE_THRESHOLD_M:
                continue

            # --- 3. Time difference ---
            comp_time = comp.get("created_at")
            if comp_time is None:
                continue
            if isinstance(comp_time, str):
                comp_time = datetime.fromisoformat(comp_time)
            if comp_time.tzinfo is None:
                comp_time = comp_time.replace(tzinfo=timezone.utc)
            if new_time.tzinfo is None:
                new_time = new_time.replace(tzinfo=timezone.utc)

            time_diff = abs((new_time - comp_time).total_seconds()) / 3600
            if time_diff > TIME_THRESHOLD_H:
                continue

            # ✅ dist is always defined here — geo check passed above
            logging.info(
                f"Duplicate detected — similarity={sim:.3f}, "
                f"distance={dist:.1f}m, "
                f"time_diff={time_diff:.1f}h, "
                f"matched_id={comp.get('_id')}"
            )
            return {"is_duplicate": True, "duplicate_of": str(comp.get("_id"))}

        return {"is_duplicate": False, "duplicate_of": None}

    except Exception as e:
        logging.error(f"Duplicate check error: {e}")
        return {"is_duplicate": False, "duplicate_of": None}