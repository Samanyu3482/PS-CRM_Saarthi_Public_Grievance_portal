from app.db.mongodb import db_client
from typing import List, Optional, Dict, Any
from app.schemas.routing import DepartmentSchema, OfficerSchema

async def get_departments() -> List[DepartmentSchema]:
    cursor = db_client.db["departments"].find({})
    deps = await cursor.to_list(length=100)
    for d in deps:
        d["_id"] = str(d["_id"])
    return [DepartmentSchema(**d) for d in deps]

async def get_officers(department: Optional[str] = None, city: Optional[str] = None) -> List[OfficerSchema]:
    query = {}
    if department:
        query["department"] = department
    if city:
        query["city"] = city
        
    cursor = db_client.db["officers"].find(query)
    officers = await cursor.to_list(length=100)
    for o in officers:
        o["_id"] = str(o["_id"])
    return [OfficerSchema(**o) for o in officers]

def detect_department(description: str) -> str:
    """
    MVP Keyword matching for department assignment.
    """
    desc = description.lower()
    if any(word in desc for word in ["water", "leak", "pipe", "plumb"]):
        return "Water Supply Department"
    if any(word in desc for word in ["power", "electric", "wire", "light"]):
        return "Electricity Department"
    if any(word in desc for word in ["garbage", "trash", "waste", "clean"]):
        return "Sanitation Department"
    if any(word in desc for word in ["road", "pothole", "street"]):
        return "Public Works Department (PWD)"
    if any(word in desc for word in ["health", "hospital", "clinic", "doctor"]):
        return "Health Department"
    
    return "Municipal Corporation"  # Fallback

async def assign_officer(department: str, city: str) -> Optional[Dict[str, Any]]:
    """
    Finds the officer with the least workload in the given department and city.
    """
    # Query matching officers, sorted by workload ascending to instantly grab the one with the smallest workload
    cursor = db_client.db["officers"].find(
        {"department": department, "city": city}
    ).sort("current_workload", 1).limit(1)
    
    officers = await cursor.to_list(length=1)
    if not officers:
        return None
        
    selected_officer = officers[0]
    
    # Increment their workload atomically
    await db_client.db["officers"].update_one(
        {"_id": selected_officer["_id"]},
        {"$inc": {"current_workload": 1}}
    )
    
    return selected_officer
