from app.db.database import get_db_ctx
from app.db.models import DepartmentDB, OfficerDB
from app.schemas.routing import DepartmentSchema, OfficerSchema
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update

async def get_departments() -> List[DepartmentSchema]:
    async with get_db_ctx() as session:
        stmt = select(DepartmentDB)
        result = await session.execute(stmt)
        deps = result.scalars().all()
        return [DepartmentSchema(**d.to_dict()) for d in deps]

async def get_officers(ministry: Optional[str] = None, department: Optional[str] = None, city: Optional[str] = None) -> List[OfficerSchema]:
    async with get_db_ctx() as session:
        stmt = select(OfficerDB)
        if ministry:
            stmt = stmt.where(OfficerDB.ministry == ministry)
        if department:
            stmt = stmt.where(OfficerDB.department == department)
        if city:
            stmt = stmt.where(OfficerDB.city == city)
            
        result = await session.execute(stmt)
        officers = result.scalars().all()
        return [OfficerSchema(**o.to_dict()) for o in officers]

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
    async with get_db_ctx() as session:
        # Find the officer with the least current_workload
        stmt = (
            select(OfficerDB)
            .where(OfficerDB.ministry == ministry)
            .where(OfficerDB.department == department)
            .where(OfficerDB.city == city)
            .order_by(OfficerDB.current_workload.asc())
            .limit(1)
        )
        result = await session.execute(stmt)
        officer = result.scalar_one_or_none()
        
        if not officer:
            return None
            
        # Update workload atomically
        officer.current_workload += 1
        session.add(officer)
        await session.commit()
        
        return officer.to_dict()
