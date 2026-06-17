from app.db.database import get_db_ctx
from app.db.models import ComplaintDB
from app.schemas.complaint import ComplaintCreate, ComplaintInDB, ComplaintUpdate, Feedback, Note
from app.services import routing_service
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, delete
from sqlalchemy.orm.attributes import flag_modified

async def create_complaint(complaint_in: ComplaintCreate, user_firebase_uid: str) -> ComplaintInDB:
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

    # 1. Spam check
    spam_result = check_spam(complaint_in.title, complaint_in.description)

    if spam_result["is_spam"]:
        db_complaint = ComplaintDB(
            title=complaint_in.title,
            description=complaint_in.description,
            category=None,
            location=location_data,
            images=complaint_in.images or [],
            created_by=user_firebase_uid,
            status="flagged_spam",
            priority="low",
            assigned_to=None,
            ministry=None,
            department=None,
            sub_department=None,
            duplicate_of=None,
            sentiment_score=None,
            sla_deadline=None,
            embedding=None,
            notes=[],
            feedback=None,
            is_spam=True,
            spam_matched_on=spam_result["matched_on"],
            spam_reason=spam_result["reason"],
            created_at=datetime.now(timezone.utc),
        )
        async with get_db_ctx() as session:
            session.add(db_complaint)
            await session.commit()
            await session.refresh(db_complaint)
            created_data = db_complaint.to_dict()
        return ComplaintInDB(**created_data)

    # 2. Embedding
    new_embedding = get_embedding(complaint_in.description).tolist()

    # 3. Deduplication check
    async with get_db_ctx() as session:
        stmt = (
            select(ComplaintDB)
            .where(ComplaintDB.created_by == user_firebase_uid)
            .order_by(ComplaintDB.created_at.desc())
            .limit(50)
        )
        result = await session.execute(stmt)
        existing_raw = [c.to_dict() for c in result.scalars().all()]

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

    # 4. Classification
    routing_info = await classify_complaint(
        title=complaint_in.title,
        description=complaint_in.description,
    )

    # 5. Officer assignment
    officer = await routing_service.assign_officer(
        routing_info["ministry"], routing_info["department"], complaint_in.city
    )

    assigned_to = str(officer["_id"]) if officer else None
    complaint_status = "assigned" if assigned_to else "submitted"

    db_complaint = ComplaintDB(
        title=complaint_in.title,
        description=complaint_in.description,
        category=None,
        location=location_data,
        images=complaint_in.images or [],
        created_by=user_firebase_uid,
        status=complaint_status,
        priority="medium",
        assigned_to=assigned_to,
        ministry=routing_info["ministry"],
        department=routing_info["department"],
        sub_department=routing_info["sub_department"],
        duplicate_of=None,
        sentiment_score=None,
        sla_deadline=None,
        embedding=new_embedding,
        notes=[],
        feedback=None,
        is_spam=False,
        spam_matched_on=[],
        spam_reason=None,
        created_at=datetime.now(timezone.utc),
    )
    
    async with get_db_ctx() as session:
        session.add(db_complaint)
        await session.commit()
        await session.refresh(db_complaint)
        created_data = db_complaint.to_dict()
        
    return ComplaintInDB(**created_data)

async def get_user_complaints(user_firebase_uid: str) -> List[ComplaintInDB]:
    async with get_db_ctx() as session:
        stmt = (
            select(ComplaintDB)
            .where(ComplaintDB.created_by == user_firebase_uid)
            .order_by(ComplaintDB.created_at.desc())
        )
        result = await session.execute(stmt)
        complaints = result.scalars().all()
        return [ComplaintInDB(**c.to_dict()) for c in complaints]

async def get_complaint_by_id(complaint_id: str) -> Optional[ComplaintInDB]:
    async with get_db_ctx() as session:
        stmt = select(ComplaintDB).where(ComplaintDB.id == complaint_id)
        result = await session.execute(stmt)
        comp = result.scalar_one_or_none()
        if comp:
            return ComplaintInDB(**comp.to_dict())
    return None

async def update_complaint(complaint_id: str, update_data: ComplaintUpdate) -> Optional[ComplaintInDB]:
    update_dict = {
        k: v for k, v in update_data.model_dump(exclude_unset=True).items()
        if v is not None
    }

    # Special case: False is falsy, ensure is_spam is handled explicitly
    if "is_spam" in update_data.model_dump(exclude_unset=True):
        update_dict["is_spam"] = update_data.is_spam

    if not update_dict:
        return await get_complaint_by_id(complaint_id)

    async with get_db_ctx() as session:
        stmt = select(ComplaintDB).where(ComplaintDB.id == complaint_id)
        result = await session.execute(stmt)
        comp = result.scalar_one_or_none()
        if comp:
            for k, v in update_dict.items():
                if k == "feedback" and v is not None:
                    # Serialize datetime in feedback if present
                    if isinstance(v.get("created_at"), datetime):
                        v["created_at"] = v["created_at"].isoformat()
                    setattr(comp, k, v)
                elif k == "notes" and v is not None:
                    # Serialize datetimes in notes list
                    notes_list = []
                    for n in v:
                        if isinstance(n.get("created_at"), datetime):
                            n["created_at"] = n["created_at"].isoformat()
                        notes_list.append(n)
                    setattr(comp, k, notes_list)
                else:
                    setattr(comp, k, v)
            session.add(comp)
            await session.commit()
            return ComplaintInDB(**comp.to_dict())
    return None

async def delete_complaint(complaint_id: str, user_id: str) -> bool:
    async with get_db_ctx() as session:
        stmt = (
            delete(ComplaintDB)
            .where(ComplaintDB.id == complaint_id)
            .where(ComplaintDB.created_by == user_id)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

async def add_feedback(complaint_id: str, rating: int, comment: Optional[str]) -> Optional[ComplaintInDB]:
    feedback_data = Feedback(rating=rating, comment=comment).model_dump()
    feedback_data["created_at"] = feedback_data["created_at"].isoformat()
    
    async with get_db_ctx() as session:
        stmt = select(ComplaintDB).where(ComplaintDB.id == complaint_id)
        result = await session.execute(stmt)
        comp = result.scalar_one_or_none()
        if comp:
            comp.feedback = feedback_data
            flag_modified(comp, "feedback")
            session.add(comp)
            await session.commit()
            return ComplaintInDB(**comp.to_dict())
    return None

async def add_note(complaint_id: str, user_id: str, text: str) -> Optional[ComplaintInDB]:
    note_data = Note(user_id=user_id, text=text).model_dump()
    note_data["created_at"] = note_data["created_at"].isoformat()
    
    async with get_db_ctx() as session:
        stmt = select(ComplaintDB).where(ComplaintDB.id == complaint_id)
        result = await session.execute(stmt)
        comp = result.scalar_one_or_none()
        if comp:
            if not comp.notes:
                comp.notes = []
            notes_list = list(comp.notes)
            notes_list.append(note_data)
            comp.notes = notes_list
            flag_modified(comp, "notes")
            session.add(comp)
            await session.commit()
            return ComplaintInDB(**comp.to_dict())
    return None

async def get_assigned_complaints(officer_id: str, skip: int = 0, limit: int = 50) -> List[ComplaintInDB]:
    async with get_db_ctx() as session:
        stmt = (
            select(ComplaintDB)
            .where(ComplaintDB.assigned_to == officer_id)
            .order_by(ComplaintDB.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        complaints = result.scalars().all()
        return [ComplaintInDB(**c.to_dict()) for c in complaints]

async def get_flagged_spam_complaints(skip: int = 0, limit: int = 50) -> List[ComplaintInDB]:
    async with get_db_ctx() as session:
        stmt = (
            select(ComplaintDB)
            .where(ComplaintDB.status == "flagged_spam")
            .order_by(ComplaintDB.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        complaints = result.scalars().all()
        return [ComplaintInDB(**c.to_dict()) for c in complaints]

async def get_all_complaint_locations() -> List[dict]:
    async with get_db_ctx() as session:
        stmt = select(ComplaintDB).where(ComplaintDB.is_spam == False)
        result = await session.execute(stmt)
        complaints = result.scalars().all()
        
        result_list = []
        for c in complaints:
            loc = c.location
            if loc and "coordinates" in loc and loc["coordinates"]:
                coords = loc["coordinates"]
                try:
                    lat = float(coords.get("lat"))
                    lng = float(coords.get("lng"))
                    result_list.append({
                        "lat": lat,
                        "lng": lng,
                        "category": c.category,
                        "status": c.status,
                        "title": c.title
                    })
                except (TypeError, ValueError):
                    continue
        return result_list