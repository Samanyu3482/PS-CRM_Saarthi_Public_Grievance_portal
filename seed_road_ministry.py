"""
Seed script: creates the road.ministry@gov.in user and 35 road-department complaints.
Run:  python seed_road_ministry.py
"""
import asyncio, os, random
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MINISTRY = "Ministry of Road Transport and Highways"
DEPARTMENT = "Road Infrastructure"

ROAD_COMPLAINTS = [
    ("Pothole causing accidents on NH-48", "A large pothole near KM-marker 32 has caused multiple two-wheeler skids in the past week. Immediate repair required.", "Infrastructure", "critical"),
    ("Highway divider damaged after truck collision", "The concrete divider on the Delhi-Jaipur expressway is broken for ~50 meters after a truck collision last night.", "Infrastructure", "high"),
    ("Waterlogging on state highway SH-12", "Heavy rain has led to severe waterlogging near the Yamuna bridge approach road making it impassable for small vehicles.", "Drainage", "critical"),
    ("Missing road signage near school zone", "Speed limit and school zone signs have been removed/stolen near Kendriya Vidyalaya, Sector 15.", "Public Safety", "high"),
    ("Broken streetlight on Ring Road", "Three consecutive streetlights near Pragati Maidan flyover are non-functional, causing a dark stretch.", "Electricity", "medium"),
    ("Illegal speed breakers on village road", "Unauthorized speed breakers have been placed on the Sohna-Palwal road causing damage to vehicle suspensions.", "Infrastructure", "medium"),
    ("Road surface peeling on newly constructed bypass", "The freshly constructed Faridabad bypass road surface is already peeling within 3 months of completion.", "Infrastructure", "high"),
    ("Overflowing drain on highway service road", "Drain alongside the GT Road service road is overflowing with sewage. Strong stench and hygiene risk.", "Sanitation", "high"),
    ("Bridge railing broken on Chambal bridge", "Metal railing on the Chambal river bridge is broken for 20 meters. Extremely dangerous for pedestrians and cyclists.", "Infrastructure", "critical"),
    ("Stray cattle on expressway causing hazards", "Multiple stray cattle spotted on the Lucknow-Agra expressway near KM 120. Major accident risk at night.", "Public Safety", "critical"),
    ("Faded lane markings on national highway", "White and yellow lane markings on NH-24 between Delhi and Ghaziabad have completely faded.", "Infrastructure", "medium"),
    ("Dust pollution from unpaved service road", "Service road parallel to NH-44 remains unpaved for 2 km, causing extreme dust pollution in nearby residential areas.", "Environment", "medium"),
    ("Collapsed culvert blocking rural road", "A culvert near Rampur village has collapsed, completely blocking the only road connecting to the district headquarters.", "Infrastructure", "critical"),
    ("Non-functional toll plaza CCTV cameras", "CCTV cameras at Kherki Daula toll plaza have not been working for weeks. No surveillance of toll fraud.", "Public Safety", "low"),
    ("Cracked retaining wall on hill road", "Retaining wall on the Shimla-Manali highway has developed large cracks after recent landslide. Risk of road collapse.", "Infrastructure", "critical"),
    ("Encroachment narrowing highway near market", "Illegal vendor stalls have encroached the roadside near Panipat market, reducing a 4-lane road to 2 effective lanes.", "Traffic", "high"),
    ("Poor drainage causing highway erosion", "Absence of proper drainage on NH-58 near Haridwar is causing shoulder erosion and road width reduction.", "Drainage", "high"),
    ("Unfinished flyover blocking traffic for months", "The Rajiv Chowk flyover construction has been stalled for 6 months, blocking two major lanes and causing 2-hour delays.", "Infrastructure", "critical"),
    ("Malfunctioning traffic signal at highway intersection", "Traffic signal at the NH-48/SH-12 intersection has been showing only red for 3 days. Chaos during peak hours.", "Traffic", "high"),
    ("Damaged guardrails on expressway curve", "Metal guardrails on the sharp curve near Mathura on Yamuna Expressway are dented and detached after recent accident.", "Infrastructure", "high"),
    ("Road widening debris not cleared", "Construction debris from road widening project near Meerut has been dumped on the roadside for months. Eye-sore and safety hazard.", "Sanitation", "medium"),
    ("Bus stop shelter collapsed", "The bus stop shelter on NH-10 near Rohtak collapsed during last week's storm. No repair initiated yet.", "Infrastructure", "medium"),
    ("Pedestrian underpass flooded", "The pedestrian underpass near ISBT Kashmere Gate is permanently waterlogged. Citizens forced to cross the highway on foot.", "Drainage", "high"),
    ("Missing rumble strips on accident-prone stretch", "Despite being identified as a black spot, the Jaipur highway stretch near Dharuhera still lacks rumble strips.", "Public Safety", "high"),
    ("Truck overloading damaging rural road", "Overloaded trucks from nearby quarry are destroying the rural road connecting villages to the state highway.", "Infrastructure", "medium"),
    ("No emergency phone on expressway", "Emergency call booths on the Eastern Peripheral Expressway are either vandalized or non-functional.", "Public Safety", "medium"),
    ("Noise barriers missing near residential colony", "The elevated highway near Dwarka Sector 21 lacks noise barriers. Residents suffering from constant traffic noise since 2023.", "Environment", "low"),
    ("Improper road restoration after pipeline work", "After GAIL pipeline work, the road surface on NH-2 near Agra was improperly restored. Uneven surface causes vehicle damage.", "Infrastructure", "high"),
    ("Dangerous open manhole on highway median", "An uncovered manhole on the highway median near Chandigarh is a major hazard. Multiple near-miss incidents reported.", "Public Safety", "critical"),
    ("Flyover expansion joints causing tyre blowouts", "Expansion joints on the Iffco Chowk flyover have protruded, causing frequent tyre blowouts for motorcycles.", "Infrastructure", "high"),
    ("Lack of reflectors on service road curves", "Service road near Manesar industrial area has sharp curves with no reflectors. Night-time accidents are increasing.", "Public Safety", "medium"),
    ("Abandoned construction vehicles blocking highway", "Two construction vehicles have been abandoned on NH-48 near Bilaspur toll for over a month, narrowing the lane.", "Traffic", "medium"),
    ("Solar-powered blinker lights not working", "All 8 solar blinker warning lights installed on the Gurgaon-Sohna road are non-functional.", "Electricity", "low"),
    ("Heavy vehicle parking on highway shoulder", "Trucks are parking on the highway shoulder near Dharuhera, forcing traffic into the main lanes dangerously.", "Traffic", "medium"),
    ("Road cave-in near underground metro construction", "A portion of the road near Huda City Centre metro station has caved in due to underground tunneling work.", "Infrastructure", "critical"),
]

STATUSES = ["submitted", "classified", "assigned", "in_progress", "resolved", "closed"]
CITIES = ["New Delhi", "Gurugram", "Jaipur", "Lucknow", "Chandigarh", "Agra", "Meerut", "Faridabad"]
STATES = {"New Delhi": "Delhi", "Gurugram": "Haryana", "Jaipur": "Rajasthan", "Lucknow": "Uttar Pradesh",
          "Chandigarh": "Chandigarh", "Agra": "Uttar Pradesh", "Meerut": "Uttar Pradesh", "Faridabad": "Haryana"}
SUB_DEPARTMENTS = ["National Highways", "State Highways", "Rural Roads", "Expressways", "Bridge & Tunnels"]

async def seed():
    mongo_uri = os.getenv("MONGODB_URI")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.get_default_database("pscrm")

    # ── 1. Seed the ministry user ────────────────────────────
    import bcrypt
    password_hash = bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode()

    user_doc = {
        "name": "Dr. Rajesh Kumar Singh",
        "email": "road.ministry@gov.in",
        "phone": "9876500001",
        "role": "ministry",
        "ministry_name": MINISTRY,
        "designation": "Joint Secretary",
        "employee_id": "MIN-ROAD-001",
        "password_hash": password_hash,
        "firebase_uid": "road_ministry_uid",
    }
    await db["users"].update_one({"email": user_doc["email"]}, {"$set": user_doc}, upsert=True)
    print(f"✅ Seeded user: {user_doc['email']}")

    # ── 2. Seed road-department complaints ───────────────────
    now = datetime.now(timezone.utc)
    # Grab some citizen IDs
    citizens = await db["users"].find({"role": "citizen"}).to_list(length=10)
    citizen_ids = [c.get("firebase_uid") or str(c["_id"]) for c in citizens] if citizens else ["citizen_placeholder"]

    complaints = []
    for i, (title, desc, category, priority) in enumerate(ROAD_COMPLAINTS):
        city = random.choice(CITIES)
        state = STATES[city]
        status = random.choice(STATUSES)
        sub_dept = random.choice(SUB_DEPARTMENTS)
        created_at = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))

        complaint = {
            "title": title,
            "description": desc,
            "category": category,
            "status": status,
            "priority": priority,
            "ministry": MINISTRY,
            "department": DEPARTMENT,
            "sub_department": sub_dept,
            "location": {
                "address": f"KM {random.randint(1, 200)}, Highway stretch",
                "city": city,
                "state": state,
                "pincode": str(random.randint(110001, 302001)),
                "coordinates": {
                    "lat": 28.6139 + random.uniform(-2.0, 2.0),
                    "lng": 77.2090 + random.uniform(-2.0, 2.0),
                },
            },
            "created_by": random.choice(citizen_ids),
            "created_at": created_at,
            "images": [],
            "notes": [],
            "is_spam": False,
            "spam_matched_on": [],
        }

        if status in ("resolved", "closed"):
            complaint["feedback"] = {
                "rating": random.randint(3, 5),
                "comment": random.choice([
                    "Issue was fixed promptly.", "Good work by the department.",
                    "Took longer than expected but resolved.", "Satisfactory resolution.",
                ]),
                "created_at": created_at + timedelta(days=random.randint(1, 5)),
            }

        if status in ("assigned", "in_progress", "resolved", "closed"):
            complaint["assigned_to"] = "road_ministry_uid"

        if status != "submitted":
            complaint["sla_deadline"] = created_at + timedelta(days=random.choice([7, 14, 21]))

        complaints.append(complaint)

    # Delete old road ministry complaints and re-seed
    del_result = await db["complaints"].delete_many({"ministry": MINISTRY})
    print(f"🗑️  Deleted {del_result.deleted_count} old road-ministry complaints")

    result = await db["complaints"].insert_many(complaints)
    print(f"✅ Seeded {len(result.inserted_ids)} road-department complaints")

    client.close()

if __name__ == "__main__":
    asyncio.run(seed())
