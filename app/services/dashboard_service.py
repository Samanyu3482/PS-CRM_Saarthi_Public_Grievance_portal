from app.db.mongodb import db_client
from typing import Dict, Any, List, Optional

async def get_citizen_dashboard(firebase_uid: str) -> Dict[str, Any]:
    pipeline = [
        {"$match": {"created_by": firebase_uid}},
        {"$facet": {
            "total": [{"$count": "count"}],
            "pending": [{"$match": {"status": "submitted"}}, {"$count": "count"}],
            "in_progress": [{"$match": {"status": {"$in": ["assigned", "in_progress", "classified"]}}}, {"$count": "count"}],
            "resolved": [{"$match": {"status": {"$in": ["resolved", "closed"]}}}, {"$count": "count"}],
            "recent": [{"$sort": {"created_at": -1}}, {"$limit": 5}]
        }}
    ]
    docs = await db_client.db["complaints"].aggregate(pipeline).to_list(1)
    data = docs[0] if docs else {}
    
    def get_count(key):
        return data.get(key, [{"count": 0}])[0]["count"] if data.get(key) else 0

    recent = []
    for c in data.get("recent", []):
        c["_id"] = str(c["_id"])
        recent.append(c)

    return {
        "total_complaints": get_count("total"),
        "pending": get_count("pending"),
        "in_progress": get_count("in_progress"),
        "resolved": get_count("resolved"),
        "recent_complaints": recent
    }

async def get_officer_dashboard(department: str) -> Dict[str, Any]:
    pipeline = [
        {"$match": {"department": department}},
        {"$facet": {
            "assigned": [{"$count": "count"}],
            "pending": [{"$match": {"status": "assigned"}}, {"$count": "count"}],
            "in_progress": [{"$match": {"status": "in_progress"}}, {"$count": "count"}],
            "resolved": [{"$match": {"status": {"$in": ["resolved", "closed"]}}}, {"$count": "count"}]
        }}
    ]
    docs = await db_client.db["complaints"].aggregate(pipeline).to_list(1)
    data = docs[0] if docs else {}
    
    def get_count(key):
        return data.get(key, [{"count": 0}])[0]["count"] if data.get(key) else 0

    return {
        "assigned_complaints": get_count("assigned"),
        "pending": get_count("pending"),
        "in_progress": get_count("in_progress"),
        "resolved": get_count("resolved"),
        "sla_breaches": 0  # Placeholder for future expansion
    }

async def get_officer_performance(department: str) -> Dict[str, Any]:
    return {
        "average_resolution_time_days": 2.5,
        "total_resolved": await db_client.db["complaints"].count_documents({"department": department, "status": "resolved"}),
        "workload": await db_client.db["complaints"].count_documents({"department": department, "status": {"$nin": ["resolved", "closed"]}})
    }

async def get_region_dashboard(state: str, city: Optional[str] = None) -> Dict[str, Any]:
    match_q: Dict[str, Any] = {"location.state": state} if state else {}
    if city:
        match_q["location.city"] = city

    pipeline = [
        {"$match": match_q},
        {"$facet": {
            "total": [{"$count": "count"}],
            "pending": [{"$match": {"status": "submitted"}}, {"$count": "count"}],
            "resolved": [{"$match": {"status": {"$in": ["resolved", "closed"]}}}, {"$count": "count"}],
            "top_issues": [
                {"$group": {"_id": "$category", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
        }}
    ]
    docs = await db_client.db["complaints"].aggregate(pipeline).to_list(1)
    data = docs[0] if docs else {}

    def get_count(key):
        return data.get(key, [{"count": 0}])[0]["count"] if data.get(key) else 0

    top_issues = [{"category": item["_id"] or "Uncategorized", "count": item["count"]} for item in data.get("top_issues", [])]

    return {
        "total_complaints": get_count("total"),
        "pending": get_count("pending"),
        "resolved": get_count("resolved"),
        "top_issues": top_issues
    }

async def get_admin_dashboard() -> Dict[str, Any]:
    pipeline = [
        {"$facet": {
            "total": [{"$count": "count"}],
            "pending": [{"$match": {"status": "submitted"}}, {"$count": "count"}],
            "resolved": [{"$match": {"status": {"$in": ["resolved", "closed"]}}}, {"$count": "count"}]
        }}
    ]
    docs = await db_client.db["complaints"].aggregate(pipeline).to_list(1)
    data = docs[0] if docs else {}

    def get_count(key):
        return data.get(key, [{"count": 0}])[0]["count"] if data.get(key) else 0

    return {
        "total_complaints": get_count("total"),
        "pending": get_count("pending"),
        "resolved": get_count("resolved"),
        "avg_resolution_time": 4.5,
        "sla_compliance": 87
    }


async def get_ministry_dashboard(ministry_name: str) -> Dict[str, Any]:
    """Aggregate dashboard data for a specific ministry."""
    match_stage = {"$match": {"ministry": ministry_name}}

    pipeline = [
        match_stage,
        {"$facet": {
            "total": [{"$count": "count"}],
            # ── Status breakdown ──
            "submitted": [{"$match": {"status": "submitted"}}, {"$count": "count"}],
            "classified": [{"$match": {"status": "classified"}}, {"$count": "count"}],
            "assigned": [{"$match": {"status": "assigned"}}, {"$count": "count"}],
            "in_progress": [{"$match": {"status": "in_progress"}}, {"$count": "count"}],
            "resolved": [{"$match": {"status": {"$in": ["resolved", "closed"]}}}, {"$count": "count"}],
            # ── Priority breakdown ──
            "priority_low": [{"$match": {"priority": "low"}}, {"$count": "count"}],
            "priority_medium": [{"$match": {"priority": "medium"}}, {"$count": "count"}],
            "priority_high": [{"$match": {"priority": "high"}}, {"$count": "count"}],
            "priority_critical": [{"$match": {"priority": "critical"}}, {"$count": "count"}],
            # ── Top 5 categories ──
            "top_categories": [
                {"$group": {"_id": "$category", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 5},
            ],
            # ── Regional breakdown (by city) ──
            "by_city": [
                {"$group": {"_id": "$location.city", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 8},
            ],
            # ── 5 most recent ──
            "recent": [
                {"$sort": {"created_at": -1}},
                {"$limit": 5},
                {"$project": {
                    "title": 1, "status": 1, "priority": 1,
                    "category": 1, "location.city": 1,
                    "created_at": 1,
                }},
            ],
            # ── Department performance ──
            "department_performance": [
                {"$group": {
                    "_id": "$department",
                    "total": {"$sum": 1},
                    "resolved": {"$sum": {"$cond": [{"$in": ["$status", ["resolved", "closed"]]}, 1, 0]}}
                }},
                {"$sort": {"total": -1}}
            ],
            # ── Crisis alerts ──
            "crisis_alerts": [
                {"$match": {"priority": "critical", "status": {"$nin": ["resolved", "closed"]}}},
                {"$sort": {"created_at": -1}},
                {"$limit": 5},
                {"$project": {
                    "title": 1, "status": 1, "priority": 1,
                    "category": 1, "location.city": 1,
                    "created_at": 1,
                }}
            ],
        }},
    ]

    docs = await db_client.db["complaints"].aggregate(pipeline).to_list(1)
    data = docs[0] if docs else {}

    def gc(key: str) -> int:
        return data.get(key, [{"count": 0}])[0]["count"] if data.get(key) else 0

    total = gc("total")
    resolved = gc("resolved")
    resolution_rate = round((resolved / total) * 100, 1) if total else 0.0

    # Format recent complaints
    recent = []
    for c in data.get("recent", []):
        c["_id"] = str(c["_id"])
        recent.append(c)

    top_categories = [
        {"category": item["_id"] or "Uncategorized", "count": item["count"]}
        for item in data.get("top_categories", [])
    ]

    by_city = [
        {"city": item["_id"] or "Unknown", "count": item["count"]}
        for item in data.get("by_city", [])
    ]

    # Format department performance
    dept_performance = [
        {"dept": item["_id"] or "Unassigned", "total": item["total"], "resolved": item["resolved"]}
        for item in data.get("department_performance", [])
    ]

    # Format crisis alerts
    crisis_alerts = []
    for c in data.get("crisis_alerts", []):
        c["_id"] = str(c["_id"])
        crisis_alerts.append(c)

    return {
        "ministry_name": ministry_name,
        "total_complaints": total,
        "resolution_rate": resolution_rate,
        "status_breakdown": {
            "submitted": gc("submitted"),
            "classified": gc("classified"),
            "assigned": gc("assigned"),
            "in_progress": gc("in_progress"),
            "resolved": resolved,
        },
        "priority_breakdown": {
            "low": gc("priority_low"),
            "medium": gc("priority_medium"),
            "high": gc("priority_high"),
            "critical": gc("priority_critical"),
        },
        "top_categories": top_categories,
        "by_city": by_city,
        "recent_complaints": recent,
        "department_performance": dept_performance,
        "crisis_alerts": crisis_alerts,
    }
