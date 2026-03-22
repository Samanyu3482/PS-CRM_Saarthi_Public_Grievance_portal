from app.db.mongodb import db_client
from typing import Dict, Any, List, Optional

async def get_citizen_dashboard(auth0_id: str) -> Dict[str, Any]:
    pipeline = [
        {"$match": {"created_by": auth0_id}},
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
