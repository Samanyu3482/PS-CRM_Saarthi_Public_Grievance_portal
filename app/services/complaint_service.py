from app.db.mongodb import db_client
from app.schemas.complaint import ComplaintCreate, ComplaintInDB, ComplaintUpdate, Feedback, Note
from app.services import routing_service
from typing import List, Optional
from datetime import datetime, timezone


async def create_complaint(
    complaint_in: ComplaintCreate,
    user_firebase_uid: str,
    user_name: str = "",
    user_email: str = "",
) -> ComplaintInDB:
    from app.services.ai_service import get_embedding, check_duplicate_complaint, check_spam
    from app.services.classification_service import classify_complaint
    from fastapi import HTTPException, status

    location_data = {
        "address": complaint_in.address,
        "city": complaint_in.city,
        "state": complaint_in.state,
        "pincode": complaint_in.pincode,
        "coordinates": {
            "lat": complaint_in.lat,
            "lng": complaint_in.lng
        } if (complaint_in.lat is not None and complaint_in.lng is not None) else None
    }

    # ── 1. Spam check (cheapest — runs first, no DB or ML needed) ────────────
    spam_result = check_spam(complaint_in.title, complaint_in.description)

    if spam_result["is_spam"]:
        complaint_dict = {
            "title": complaint_in.title,
            "description": complaint_in.description,
            "category": None,
            "location": location_data,
            "images": complaint_in.images or [],
            "created_by": user_firebase_uid,
            "status": "flagged_spam",
            "priority": "low",
            "assigned_to": None,
            "ministry": None,
            "department": None,
            "sub_department": None,
            "duplicate_of": None,
            "sentiment_score": None,
            "sla_deadline": None,
            "embedding": None,          # not worth indexing spam
            "notes": [],
            "feedback": None,
            "is_spam": True,
            "spam_matched_on": spam_result["matched_on"],
            "spam_reason": spam_result["reason"],
            "created_at": datetime.now(timezone.utc),
        }
        insert_result = await db_client.db["complaints"].insert_one(complaint_dict)
        created = await db_client.db["complaints"].find_one({"_id": insert_result.inserted_id})
        created["_id"] = str(created["_id"])
        return ComplaintInDB(**created)

    # ── 2. Embedding (only for clean complaints) ──────────────────────────────
    new_embedding = get_embedding(complaint_in.description).tolist()

    # ── 3. Deduplication check ────────────────────────────────────────────────
    existing_raw = await db_client.db["complaints"].find(
        {"created_by": user_firebase_uid}
    ).sort("created_at", -1).to_list(length=50)

    if existing_raw:
        dup_result = await check_duplicate_complaint(
            new_embedding=new_embedding,
            new_lat=complaint_in.lat,
            new_lng=complaint_in.lng,
            new_time=datetime.now(timezone.utc),
            existing_complaints=existing_raw,
        )
        if dup_result and dup_result["is_duplicate"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Duplicate complaint detected. A similar complaint was already "
                    f"submitted (ID: {dup_result['duplicate_of']}). "
                    "Criteria: text similarity > 80%, location within 20m, within 24h."
                ),
            )

    # ── 4. Classification (replaces routing_service.detect_department) ────────
    routing_info = await classify_complaint(
        title=complaint_in.title,
        description=complaint_in.description,
    )

    # ── 5. Officer assignment ─────────────────────────────────────────────────
    officer = await routing_service.assign_officer(
        routing_info["ministry"], routing_info["department"], complaint_in.city
    )

    assigned_to = str(officer["_id"]) if officer else None
    complaint_status = "assigned" if assigned_to else "submitted"

    complaint_dict = {
        "title": complaint_in.title,
        "description": complaint_in.description,
        "category": None,
        "location": location_data,
        "images": complaint_in.images or [],
        "created_by": user_firebase_uid,
        "status": complaint_status,
        "priority": "medium",
        "assigned_to": assigned_to,
        "ministry": routing_info["ministry"],
        "department": routing_info["department"],
        "sub_department": routing_info["sub_department"],
        "duplicate_of": None,
        "sentiment_score": None,
        "sla_deadline": None,
        "embedding": new_embedding,
        "notes": [],
        "feedback": None,
        "is_spam": False,
        "spam_matched_on": [],
        "spam_reason": None,
        "created_at": datetime.now(timezone.utc),
    }

    insert_result = await db_client.db["complaints"].insert_one(complaint_dict)
    created = await db_client.db["complaints"].find_one({"_id": insert_result.inserted_id})
    created["_id"] = str(created["_id"])

    # ── 6. Send email notifications (ministry + citizen) ──────────────────────
    print(f"📧 [MAIL] Attempting to send emails — ministry={routing_info['ministry']}, citizen={user_email}")
    try:
        from app.services.mail_service import send_complaint_emails
        send_complaint_emails(
            complaint_id=created["_id"],
            title=complaint_in.title,
            description=complaint_in.description,
            ministry=routing_info["ministry"],
            department=routing_info["department"],
            location=location_data,
            priority="medium",
            citizen_name=user_name or "Citizen",
            citizen_email=user_email,
        )
        print("✅ [MAIL] Emails sent successfully!")
    except Exception as e:
        print(f"❌ [MAIL] Email notification failed: {type(e).__name__}: {e}")
        import logging, traceback
        logging.getLogger(__name__).exception("Email notification failed — complaint was still saved.")

    return ComplaintInDB(**created)


async def get_user_complaints(user_firebase_uid: str) -> List[ComplaintInDB]:
    cursor = db_client.db["complaints"].find(
        {"created_by": user_firebase_uid}
    ).sort("created_at", -1)
    complaints = await cursor.to_list(length=100)
    result = []
    for comp in complaints:
        comp["_id"] = str(comp["_id"])
        result.append(ComplaintInDB(**comp))
    return result


async def get_complaint_by_id(complaint_id: str) -> Optional[ComplaintInDB]:
    from bson import ObjectId
    try:
        obj_id = ObjectId(complaint_id)
    except Exception:
        return None
    comp = await db_client.db["complaints"].find_one({"_id": obj_id})
    if comp:
        comp["_id"] = str(comp["_id"])
        return ComplaintInDB(**comp)
    return None


async def update_complaint(complaint_id: str, update_data: ComplaintUpdate) -> Optional[ComplaintInDB]:
    from bson import ObjectId
    try:
        obj_id = ObjectId(complaint_id)
    except Exception:
        return None

    update_dict = {
        k: v for k, v in update_data.model_dump(exclude_unset=True).items()
        if v is not None
    }

    # ── Special case: officer clearing a spam flag ────────────────────────────
    # is_spam=False is a valid update but gets filtered by "if v is not None"
    # since False is falsy — handle explicitly
    if "is_spam" in update_data.model_dump(exclude_unset=True):
        update_dict["is_spam"] = update_data.is_spam

    if not update_dict:
        return await get_complaint_by_id(complaint_id)

    await db_client.db["complaints"].update_one(
        {"_id": obj_id}, {"$set": update_dict}
    )
    return await get_complaint_by_id(complaint_id)


async def delete_complaint(complaint_id: str, user_id: str) -> bool:
    """Delete a complaint if the user is the creator."""
    from bson import ObjectId
    try:
        obj_id = ObjectId(complaint_id)
    except Exception:
        return False
        
    result = await db_client.db["complaints"].delete_one(
        {"_id": obj_id, "created_by": user_id}
    )
    return result.deleted_count > 0



async def add_feedback(complaint_id: str, rating: int, comment: Optional[str]) -> Optional[ComplaintInDB]:
    from bson import ObjectId
    try:
        obj_id = ObjectId(complaint_id)
    except Exception:
        return None
    feedback_data = Feedback(rating=rating, comment=comment).model_dump()
    await db_client.db["complaints"].update_one(
        {"_id": obj_id}, {"$set": {"feedback": feedback_data}}
    )
    return await get_complaint_by_id(complaint_id)


async def add_note(complaint_id: str, user_id: str, text: str) -> Optional[ComplaintInDB]:
    from bson import ObjectId
    try:
        obj_id = ObjectId(complaint_id)
    except Exception:
        return None
    note_data = Note(user_id=user_id, text=text).model_dump()
    await db_client.db["complaints"].update_one(
        {"_id": obj_id}, {"$push": {"notes": note_data}}
    )
    return await get_complaint_by_id(complaint_id)


async def get_assigned_complaints(officer_id: str, skip: int = 0, limit: int = 50) -> List[ComplaintInDB]:
    cursor = db_client.db["complaints"].find(
        {"assigned_to": officer_id}
    ).sort("created_at", -1).skip(skip).limit(limit)
    complaints = await cursor.to_list(length=limit)
    result = []
    for comp in complaints:
        comp["_id"] = str(comp["_id"])
        result.append(ComplaintInDB(**comp))
    return result


async def get_flagged_spam_complaints(skip: int = 0, limit: int = 50) -> List[ComplaintInDB]:
    """Fetch all spam-flagged complaints for officer review."""
    cursor = db_client.db["complaints"].find(
        {"status": "flagged_spam"}
    ).sort("created_at", -1).skip(skip).limit(limit)
    complaints = await cursor.to_list(length=limit)
    result = []
    for comp in complaints:
        comp["_id"] = str(comp["_id"])
        result.append(ComplaintInDB(**comp))
    return result


async def get_all_complaint_locations() -> List[dict]:
    """Fetch coordinates, category, and status of all complaints for heatmap."""
    cursor = db_client.db["complaints"].find(
        {"location.coordinates": {"$ne": None}, "is_spam": {"$ne": True}},
        {"location.coordinates": 1, "category": 1, "status": 1, "title": 1, "created_at": 1}
    )
    complaints = await cursor.to_list(length=1000)
    result = []
    for comp in complaints:
        if comp.get("location") and comp["location"].get("coordinates"):
            coords = comp["location"]["coordinates"]
            try:
                lat = float(coords.get("lat"))
                lng = float(coords.get("lng"))
            except (TypeError, ValueError):
                continue

            result.append({
                "lat": lat,
                "lng": lng,
                "category": comp.get("category"),
                "status": comp.get("status"),
                "title": comp.get("title")
            })
    return result