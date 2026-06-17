from app.db.database import get_db_ctx
from app.db.models import ComplaintDB
from typing import List, Dict, Any
from sqlalchemy import func, select

async def get_heatmap() -> List[Dict[str, Any]]:
    city_expr = func.jsonb_extract_path_text(ComplaintDB.location, 'city')
    async with get_db_ctx() as session:
        stmt = (
            select(city_expr.label("city"), func.count().label("count"))
            .where(city_expr.isnot(None))
            .group_by(city_expr)
            .order_by(func.count().desc())
            .limit(100)
        )
        result = await session.execute(stmt)
        rows = result.all()
        return [{"location": row.city, "count": row.count} for row in rows if row.city]

async def get_trends() -> List[Dict[str, Any]]:
    month_expr = func.extract('month', ComplaintDB.created_at)
    async with get_db_ctx() as session:
        stmt = (
            select(month_expr.label("month"), func.count().label("count"))
            .group_by(month_expr)
            .order_by(month_expr.asc())
            .limit(12)
        )
        result = await session.execute(stmt)
        rows = result.all()
        
        months_map = {1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"May", 6:"Jun", 7:"Jul", 8:"Aug", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dec"}
        return [{"month": months_map.get(int(row.month), "Unknown"), "count": row.count} for row in rows]

async def get_departments_analytics() -> List[Dict[str, Any]]:
    async with get_db_ctx() as session:
        stmt = (
            select(
                ComplaintDB.department.label("department"),
                func.count().label("total"),
                func.sum(func.case((ComplaintDB.status.in_(["resolved", "closed"]), 1), else_=0)).label("resolved"),
                func.sum(func.case((ComplaintDB.status.in_(["submitted", "assigned"]), 1), else_=0)).label("pending")
            )
            .group_by(ComplaintDB.department)
            .order_by(func.count().desc())
            .limit(100)
        )
        result = await session.execute(stmt)
        rows = result.all()
        
        return [
            {
                "department": row.department or "Unassigned",
                "resolved": int(row.resolved or 0),
                "pending": int(row.pending or 0)
            }
            for row in rows
        ]

async def get_crisis_alerts() -> List[Dict[str, Any]]:
    city_expr = func.jsonb_extract_path_text(ComplaintDB.location, 'city')
    async with get_db_ctx() as session:
        stmt = (
            select(
                city_expr.label("city"),
                ComplaintDB.department.label("department"),
                func.count().label("count")
            )
            .where(ComplaintDB.status == "submitted")
            .group_by(city_expr, ComplaintDB.department)
            .having(func.count() >= 5)
            .order_by(func.count().desc())
            .limit(50)
        )
        result = await session.execute(stmt)
        rows = result.all()
        
        return [
            {
                "area": row.city,
                "issue": row.department,
                "count": row.count,
                "alert": True
            }
            for row in rows
            if row.city and row.department
        ]
