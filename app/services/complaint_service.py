from app.db.mongodb import db_client
from app.schemas.complaint import ComplaintCreate, ComplaintInDB, ComplaintUpdate, Location, Coordinates
from app.services import routing_service
from fastapi.encoders import jsonable_encoder
from typing import List, Optional
from datetime import datetime, timezone

async def create_complaint(complaint_in: ComplaintCreate, user_auth0_id: str) -> ComplaintInDB:
    location_data = {
        "address": complaint_in.address,
        "city": complaint_in.city,
        "state": complaint_in.state,
        "pincode": complaint_in.pincode,
        "coordinates": {"lat": complaint_in.lat, "lng": complaint_in.lng} if (complaint_in.lat and complaint_in.lng) else None
    }
    
    # AI Deduplication Check
    existing_comps = await get_user_complaints(user_auth0_id)
    if existing_comps:
        from app.services.ai_service import check_duplicate_complaint
        from fastapi import HTTPException, status
        existing_descs = [c.description for c in existing_comps]
        # Compare against up to 10 recent complaints to limit Gemini token usage
        is_duplicate = await check_duplicate_complaint(complaint_in.description, existing_descs[:10])
        if is_duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate complaint detected by AI. You have already submitted this specific issue."
            )

    department = routing_service.detect_department(complaint_in.description)
    officer = await routing_service.assign_officer(department, complaint_in.city)
    
    assigned_to = str(officer["_id"]) if officer else None
    status = "assigned" if assigned_to else "submitted"

    complaint_dict = {
        "title": complaint_in.title,
        "description": complaint_in.description,
        "category": None,
        "location": location_data,
        "images": complaint_in.images or [],
        "created_by": user_auth0_id,
        "status": status,
        "priority": "medium",
        "assigned_to": assigned_to,
        "department": department,
        "duplicate_of": None,
        "sentiment_score": None,
        "sla_deadline": None,
        "created_at": datetime.now(timezone.utc)
    }
    
    result = await db_client.db["complaints"].insert_one(complaint_dict)
    created_complaint = await db_client.db["complaints"].find_one({"_id": result.inserted_id})
    if created_complaint and "_id" in created_complaint:
        created_complaint["_id"] = str(created_complaint["_id"])
        
    return ComplaintInDB(**created_complaint)

async def get_user_complaints(user_auth0_id: str) -> List[ComplaintInDB]:
    cursor = db_client.db["complaints"].find({"created_by": user_auth0_id}).sort("created_at", -1)
    complaints = await cursor.to_list(length=100)
    result = []
    for comp in complaints:
        if "_id" in comp:
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
        
    update_dict = {k: v for k, v in update_data.model_dump(exclude_unset=True).items() if v is not None}
    if not update_dict:
        return await get_complaint_by_id(complaint_id)
        
    await db_client.db["complaints"].update_one(
        {"_id": obj_id},
        {"$set": update_dict}
    )
    
    return await get_complaint_by_id(complaint_id)
