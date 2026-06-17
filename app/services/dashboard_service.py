from app.db.database import get_db_ctx
from app.db.models import ComplaintDB
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import func, select, Float, case

async def get_citizen_dashboard(firebase_uid: str) -> Dict[str, Any]:
    async with get_db_ctx() as session:
        # Total
        stmt = select(func.count()).where(ComplaintDB.created_by == firebase_uid)
        result = await session.execute(stmt)
        total = result.scalar() or 0

        # Pending
        stmt = select(func.count()).where(ComplaintDB.created_by == firebase_uid).where(ComplaintDB.status == "submitted")
        result = await session.execute(stmt)
        pending = result.scalar() or 0

        # In Progress
        stmt = (
            select(func.count())
            .where(ComplaintDB.created_by == firebase_uid)
            .where(ComplaintDB.status.in_(["assigned", "in_progress", "classified"]))
        )
        result = await session.execute(stmt)
        in_progress = result.scalar() or 0

        # Resolved
        stmt = (
            select(func.count())
            .where(ComplaintDB.created_by == firebase_uid)
            .where(ComplaintDB.status.in_(["resolved", "closed"]))
        )
        result = await session.execute(stmt)
        resolved = result.scalar() or 0

        # Recent
        stmt = (
            select(ComplaintDB)
            .where(ComplaintDB.created_by == firebase_uid)
            .order_by(ComplaintDB.created_at.desc())
            .limit(5)
        )
        result = await session.execute(stmt)
        recent = [c.to_dict() for c in result.scalars().all()]

    return {
        "total_complaints": total,
        "pending": pending,
        "in_progress": in_progress,
        "resolved": resolved,
        "recent_complaints": recent
    }

async def get_officer_dashboard(department: str) -> Dict[str, Any]:
    async with get_db_ctx() as session:
        stmt = select(func.count()).where(ComplaintDB.department == department)
        result = await session.execute(stmt)
        assigned = result.scalar() or 0

        stmt = select(func.count()).where(ComplaintDB.department == department).where(ComplaintDB.status == "assigned")
        result = await session.execute(stmt)
        pending = result.scalar() or 0

        stmt = select(func.count()).where(ComplaintDB.department == department).where(ComplaintDB.status == "in_progress")
        result = await session.execute(stmt)
        in_progress = result.scalar() or 0

        stmt = (
            select(func.count())
            .where(ComplaintDB.department == department)
            .where(ComplaintDB.status.in_(["resolved", "closed"]))
        )
        result = await session.execute(stmt)
        resolved = result.scalar() or 0

    return {
        "assigned_complaints": assigned,
        "pending": pending,
        "in_progress": in_progress,
        "resolved": resolved,
        "sla_breaches": 0
    }

async def get_officer_performance(department: str) -> Dict[str, Any]:
    async with get_db_ctx() as session:
        stmt_resolved = select(func.count()).where(ComplaintDB.department == department).where(ComplaintDB.status == "resolved")
        res_resolved = await session.execute(stmt_resolved)
        resolved = res_resolved.scalar() or 0

        stmt_workload = (
            select(func.count())
            .where(ComplaintDB.department == department)
            .where(ComplaintDB.status.notin_(["resolved", "closed"]))
        )
        res_workload = await session.execute(stmt_workload)
        workload = res_workload.scalar() or 0

    return {
        "average_resolution_time_days": 2.5,
        "total_resolved": resolved,
        "workload": workload
    }

async def get_region_dashboard(state: str, city: Optional[str] = None) -> Dict[str, Any]:
    state_expr = func.jsonb_extract_path_text(ComplaintDB.location, 'state')
    city_expr = func.jsonb_extract_path_text(ComplaintDB.location, 'city')

    async with get_db_ctx() as session:
        # Total
        stmt = select(func.count()).where(state_expr.ilike(state))
        if city:
            stmt = stmt.where(city_expr.ilike(city))
        res_total = await session.execute(stmt)
        total = res_total.scalar() or 0

        # Pending
        stmt = select(func.count()).where(state_expr.ilike(state)).where(ComplaintDB.status == "submitted")
        if city:
            stmt = stmt.where(city_expr.ilike(city))
        res_pending = await session.execute(stmt)
        pending = res_pending.scalar() or 0

        # Resolved
        stmt = (
            select(func.count())
            .where(state_expr.ilike(state))
            .where(ComplaintDB.status.in_(["resolved", "closed"]))
        )
        if city:
            stmt = stmt.where(city_expr.ilike(city))
        res_resolved = await session.execute(stmt)
        resolved = res_resolved.scalar() or 0

        # Top issues / categories
        stmt_top = (
            select(ComplaintDB.category.label("category"), func.count().label("count"))
            .where(state_expr.ilike(state))
        )
        if city:
            stmt_top = stmt_top.where(city_expr.ilike(city))
        stmt_top = stmt_top.group_by(ComplaintDB.category).order_by(func.count().desc()).limit(5)
        res_top = await session.execute(stmt_top)
        top_issues = [
            {"category": row.category or "Uncategorized", "count": row.count}
            for row in res_top.all()
        ]

    return {
        "total_complaints": total,
        "pending": pending,
        "resolved": resolved,
        "top_issues": top_issues
    }

async def get_admin_dashboard() -> Dict[str, Any]:
    async with get_db_ctx() as session:
        stmt = select(func.count())
        res_total = await session.execute(stmt)
        total = res_total.scalar() or 0

        stmt = select(func.count()).where(ComplaintDB.status == "submitted")
        res_pending = await session.execute(stmt)
        pending = res_pending.scalar() or 0

        stmt = select(func.count()).where(ComplaintDB.status.in_(["resolved", "closed"]))
        res_resolved = await session.execute(stmt)
        resolved = res_resolved.scalar() or 0

    return {
        "total_complaints": total,
        "pending": pending,
        "resolved": resolved,
        "avg_resolution_time": 4.5,
        "sla_compliance": 87
    }

async def get_ministry_dashboard(ministry_name: str) -> Dict[str, Any]:
    city_expr = func.jsonb_extract_path_text(ComplaintDB.location, 'city')
    async with get_db_ctx() as session:
        stmt = select(func.count()).where(ComplaintDB.ministry == ministry_name)
        total = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(ComplaintDB.ministry == ministry_name).where(ComplaintDB.status == "submitted")
        submitted = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(ComplaintDB.ministry == ministry_name).where(ComplaintDB.status == "classified")
        classified = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(ComplaintDB.ministry == ministry_name).where(ComplaintDB.status == "assigned")
        assigned = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(ComplaintDB.ministry == ministry_name).where(ComplaintDB.status == "in_progress")
        in_progress = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(ComplaintDB.ministry == ministry_name).where(ComplaintDB.status.in_(["resolved", "closed"]))
        resolved = (await session.execute(stmt)).scalar() or 0

        # Priorities
        stmt = select(func.count()).where(ComplaintDB.ministry == ministry_name).where(ComplaintDB.priority == "low")
        low = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(ComplaintDB.ministry == ministry_name).where(ComplaintDB.priority == "medium")
        medium = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(ComplaintDB.ministry == ministry_name).where(ComplaintDB.priority == "high")
        high = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(ComplaintDB.ministry == ministry_name).where(ComplaintDB.priority == "critical")
        critical = (await session.execute(stmt)).scalar() or 0

        # Top Categories
        stmt = (
            select(ComplaintDB.category, func.count())
            .where(ComplaintDB.ministry == ministry_name)
            .group_by(ComplaintDB.category)
            .order_by(func.count().desc())
            .limit(5)
        )
        top_categories = [{"category": r[0] or "Uncategorized", "count": r[1]} for r in (await session.execute(stmt)).all()]

        # Cities
        stmt = (
            select(city_expr, func.count())
            .where(ComplaintDB.ministry == ministry_name)
            .group_by(city_expr)
            .order_by(func.count().desc())
            .limit(8)
        )
        by_city = [{"city": r[0] or "Unknown", "count": r[1]} for r in (await session.execute(stmt)).all()]

        # Recent
        stmt = (
            select(ComplaintDB)
            .where(ComplaintDB.ministry == ministry_name)
            .order_by(ComplaintDB.created_at.desc())
            .limit(5)
        )
        recent = [c.to_dict() for c in (await session.execute(stmt)).scalars().all()]

    resolution_rate = round((resolved / total) * 100, 1) if total else 0.0

    return {
        "ministry_name": ministry_name,
        "total_complaints": total,
        "resolution_rate": resolution_rate,
        "status_breakdown": {
            "submitted": submitted,
            "classified": classified,
            "assigned": assigned,
            "in_progress": in_progress,
            "resolved": resolved,
        },
        "priority_breakdown": {
            "low": low,
            "medium": medium,
            "high": high,
            "critical": critical,
        },
        "top_categories": top_categories,
        "by_city": by_city,
        "recent_complaints": recent,
    }

async def get_delhi_cm_dashboard() -> Dict[str, Any]:
    state_expr = func.jsonb_extract_path_text(ComplaintDB.location, 'state')
    city_expr = func.jsonb_extract_path_text(ComplaintDB.location, 'city')

    async with get_db_ctx() as session:
        # Total
        stmt = select(func.count()).where(state_expr.ilike("delhi"))
        total = (await session.execute(stmt)).scalar() or 0

        # Statuses
        stmt = select(func.count()).where(state_expr.ilike("delhi")).where(ComplaintDB.status == "submitted")
        submitted = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(state_expr.ilike("delhi")).where(ComplaintDB.status == "classified")
        classified = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(state_expr.ilike("delhi")).where(ComplaintDB.status == "assigned")
        assigned = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(state_expr.ilike("delhi")).where(ComplaintDB.status == "in_progress")
        in_progress = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(state_expr.ilike("delhi")).where(ComplaintDB.status.in_(["resolved", "closed"]))
        resolved = (await session.execute(stmt)).scalar() or 0

        # Priorities
        stmt = select(func.count()).where(state_expr.ilike("delhi")).where(ComplaintDB.priority == "low")
        low = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(state_expr.ilike("delhi")).where(ComplaintDB.priority == "medium")
        medium = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(state_expr.ilike("delhi")).where(ComplaintDB.priority == "high")
        high = (await session.execute(stmt)).scalar() or 0

        stmt = select(func.count()).where(state_expr.ilike("delhi")).where(ComplaintDB.priority == "critical")
        critical = (await session.execute(stmt)).scalar() or 0

        # Top categories
        stmt = (
            select(ComplaintDB.category, func.count())
            .where(state_expr.ilike("delhi"))
            .group_by(ComplaintDB.category)
            .order_by(func.count().desc())
            .limit(5)
        )
        top_categories = [{"category": r[0] or "Uncategorized", "count": r[1]} for r in (await session.execute(stmt)).all()]

        # Districts (by city)
        stmt = (
            select(city_expr, func.count())
            .where(state_expr.ilike("delhi"))
            .group_by(city_expr)
            .order_by(func.count().desc())
            .limit(10)
        )
        by_city = [{"city": r[0] or "Unknown", "count": r[1]} for r in (await session.execute(stmt)).all()]

        # Recent complaints
        stmt = (
            select(ComplaintDB)
            .where(state_expr.ilike("delhi"))
            .order_by(ComplaintDB.created_at.desc())
            .limit(5)
        )
        recent = [c.to_dict() for c in (await session.execute(stmt)).scalars().all()]

        # Crisis alerts (critical status, not resolved)
        stmt = (
            select(ComplaintDB)
            .where(state_expr.ilike("delhi"))
            .where(ComplaintDB.priority == "critical")
            .where(ComplaintDB.status.notin_(["resolved", "closed"]))
            .order_by(ComplaintDB.created_at.desc())
            .limit(5)
        )
        crisis_alerts = [c.to_dict() for c in (await session.execute(stmt)).scalars().all()]

        # Department performance
        stmt = (
            select(
                ComplaintDB.department.label("department"),
                func.count().label("total"),
                func.sum(
                    case(
                        (ComplaintDB.status.in_(["resolved", "closed"]), 1),
                        else_=0
                    )
                ).label("resolved")
            )
            .where(state_expr.ilike("delhi"))
            .where(ComplaintDB.department.isnot(None))
            .group_by(ComplaintDB.department)
            .order_by(func.count().desc())
            .limit(10)
        )
        rows_perf = (await session.execute(stmt)).all()
        department_performance = [
            {"dept": row.department, "total": int(row.total or 0), "resolved": int(row.resolved or 0)}
            for row in rows_perf
        ]

        # Ratings
        rating_expr = func.cast(func.jsonb_extract_path_text(ComplaintDB.feedback, 'rating'), Float)
        stmt = (
            select(
                ComplaintDB.department.label("department"),
                func.avg(rating_expr).label("average_rating"),
                func.count(rating_expr).label("total_feedbacks")
            )
            .where(state_expr.ilike("delhi"))
            .where(ComplaintDB.department.isnot(None))
            .where(func.jsonb_extract_path_text(ComplaintDB.feedback, 'rating').isnot(None))
            .group_by(ComplaintDB.department)
            .order_by(func.avg(rating_expr).desc())
            .limit(50)
        )
        rows_fb = (await session.execute(stmt)).all()
        department_feedback = [
            {
                "department": row.department,
                "average_rating": round(float(row.average_rating or 0.0), 1),
                "total_feedbacks": int(row.total_feedbacks or 0)
            }
            for row in rows_fb
        ]

    resolution_rate = round((resolved / total) * 100, 1) if total else 0.0

    return {
        "total_complaints": total,
        "resolution_rate": resolution_rate,
        "status_breakdown": {
            "submitted": submitted,
            "classified": classified,
            "assigned": assigned,
            "in_progress": in_progress,
            "resolved": resolved,
        },
        "priority_breakdown": {
            "low": low,
            "medium": medium,
            "high": high,
            "critical": critical,
        },
        "top_categories": top_categories,
        "by_city": by_city,
        "recent_complaints": recent,
        "crisis_alerts": crisis_alerts,
        "department_performance": department_performance,
        "department_feedback": department_feedback
    }
