from app.db.mongodb import db_client
from typing import List, Dict, Any

async def get_heatmap() -> List[Dict[str, Any]]:
    pipeline = [
        {"$group": {
            "_id": "$location.city",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]
    docs = await db_client.db["complaints"].aggregate(pipeline).to_list(100)
    return [{"location": d["_id"], "count": d["count"]} for d in docs if d["_id"]]

async def get_trends() -> List[Dict[str, Any]]:
    # Simplifying trend by grouping by month using MongoDB projection
    pipeline = [
        {"$group": {
            "_id": {"$month": "$created_at"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    docs = await db_client.db["complaints"].aggregate(pipeline).to_list(12)
    months_map = {1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"May", 6:"Jun", 7:"Jul", 8:"Aug", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dec"}
    return [{"month": months_map.get(d["_id"], "Unknown"), "count": d["count"]} for d in docs]

async def get_departments_analytics() -> List[Dict[str, Any]]:
    pipeline = [
        {"$group": {
            "_id": "$department",
            "total": {"$sum": 1},
            "resolved": {"$sum": {"$cond": [{"$in": ["$status", ["resolved", "closed"]]}, 1, 0]}},
            "pending": {"$sum": {"$cond": [{"$in": ["$status", ["submitted", "assigned"]]}, 1, 0]}}
        }},
        {"$sort": {"total": -1}}
    ]
    docs = await db_client.db["complaints"].aggregate(pipeline).to_list(100)
    return [{"department": d["_id"] or "Unassigned", "resolved": d["resolved"], "pending": d["pending"]} for d in docs]

async def get_crisis_alerts() -> List[Dict[str, Any]]:
    pipeline = [
        {"$match": {"status": "submitted"}},
        {"$group": {
            "_id": {"city": "$location.city", "department": "$department"},
            "count": {"$sum": 1}
        }},
        {"$match": {"count": {"$gte": 5}}}, # Arbitrary MVP threshold for crisis
        {"$sort": {"count": -1}}
    ]
    docs = await db_client.db["complaints"].aggregate(pipeline).to_list(50)
    return [{"area": d["_id"]["city"], "issue": d["_id"]["department"], "count": d["count"], "alert": True} for d in docs if d["_id"]["city"] and d["_id"]["department"]]
