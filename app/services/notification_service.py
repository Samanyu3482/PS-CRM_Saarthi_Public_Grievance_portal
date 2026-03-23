from app.db.mongodb import db_client
from app.schemas.notification import NotificationInDB
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timezone

async def create_notification(user_id: str, message: str) -> NotificationInDB:
    notification_dict = {
        "user_id": user_id,
        "message": message,
        "is_read": False,
        "created_at": datetime.now(timezone.utc)
    }
    
    result = await db_client.db["notifications"].insert_one(notification_dict)
    created_notification = await db_client.db["notifications"].find_one({"_id": result.inserted_id})
    if created_notification and "_id" in created_notification:
        created_notification["_id"] = str(created_notification["_id"])
        
    return NotificationInDB(**created_notification)

async def get_user_notifications(user_id: str, skip: int = 0, limit: int = 50) -> List[NotificationInDB]:
    cursor = db_client.db["notifications"].find({"user_id": user_id}).sort("created_at", -1).skip(skip).limit(limit)
    notifications = await cursor.to_list(length=limit)
    result = []
    for n in notifications:
        if "_id" in n:
            n["_id"] = str(n["_id"])
        result.append(NotificationInDB(**n))
    return result

async def mark_as_read(notification_id: str) -> Optional[NotificationInDB]:
    try:
        obj_id = ObjectId(notification_id)
    except Exception:
        return None
        
    await db_client.db["notifications"].update_one(
        {"_id": obj_id},
        {"$set": {"is_read": True}}
    )
    
    n = await db_client.db["notifications"].find_one({"_id": obj_id})
    if n:
        n["_id"] = str(n["_id"])
        return NotificationInDB(**n)
    return None
