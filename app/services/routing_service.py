from app.db.mongodb import db_client
from typing import List, Optional, Dict, Any
from app.schemas.routing import DepartmentSchema, OfficerSchema

async def get_departments() -> List[DepartmentSchema]:
    cursor = db_client.db["departments"].find({})
    deps = await cursor.to_list(length=100)
    for d in deps:
        d["_id"] = str(d["_id"])
    return [DepartmentSchema(**d) for d in deps]

async def get_officers(ministry: Optional[str] = None, department: Optional[str] = None, city: Optional[str] = None) -> List[OfficerSchema]:
    query = {}
    if ministry:
        query["ministry"] = ministry
    if department:
        query["department"] = department
    if city:
        query["city"] = city
        
    cursor = db_client.db["officers"].find(query)
    officers = await cursor.to_list(length=100)
    for o in officers:
        o["_id"] = str(o["_id"])
    return [OfficerSchema(**o) for o in officers]

def detect_department(description: str) -> Dict[str, str]:
    """
    MVP Keyword matching for department assignment.
    """
    desc = description.lower()
    
    if any(word in desc for word in ["tax", "income", "gst", "customs"]):
        return {"ministry": "Ministry of Finance", "department": "Department of Revenue", "sub_department": "Income Tax Department"}
    if any(word in desc for word in ["bank", "insurance", "pension", "pfrda"]):
        return {"ministry": "Ministry of Finance", "department": "Department of Financial Services", "sub_department": "Public Sector Banks"}
    if any(word in desc for word in ["train", "ticket", "railway", "platform", "refund"]):
        return {"ministry": "Ministry of Railways", "department": "Railway Board", "sub_department": "Passenger Complaints"}
    if any(word in desc for word in ["gas", "cylinder", "petrol", "fuel", "lpg"]):
        return {"ministry": "Ministry of Petroleum and Natural Gas", "department": "Oil Marketing Companies", "sub_department": "LPG Subsidy"}
    if any(word in desc for word in ["pf", "uan", "esi", "hospital", "claim"]):
        return {"ministry": "Ministry of Labour and Employment", "department": "EPFO", "sub_department": "PF Withdrawal"}
    if any(word in desc for word in ["municipal", "cpwd", "dda", "road", "pothole", "garbage", "trash"]):
        return {"ministry": "Ministry of Housing and Urban Affairs", "department": "Urban Bodies", "sub_department": "Municipal Services"}
    if any(word in desc for word in ["electricity", "power", "cut", "bill", "light", "wire"]):
        return {"ministry": "Ministry of Power", "department": "Electricity Services", "sub_department": "Billing Issues"}
    if any(word in desc for word in ["call", "network", "drop", "post", "parcel", "speed"]):
        return {"ministry": "Ministry of Communications", "department": "Telecom", "sub_department": "Network Issues"}
    
    # Fallback default
    return {"ministry": "Ministry of Housing and Urban Affairs", "department": "Urban Bodies", "sub_department": "Municipal Services"}

async def assign_officer(ministry: str, department: str, city: str) -> Optional[Dict[str, Any]]:
    """
    Finds the officer with the least workload in the given department and city.
    """
    # Query matching officers, sorted by workload ascending to instantly grab the one with the smallest workload
    cursor = db_client.db["officers"].find(
        {"ministry": ministry, "department": department, "city": city}
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
