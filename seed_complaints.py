import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timedelta, timezone
import random
from dotenv import load_dotenv

async def seed_complaints():
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB_NAME", "pscrm")
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    
    # Sample Titles and Categories
    samples = [
        ("Pothole on Main Road", "Infrastructure", "High"),
        ("Street Light Not Working in Sector 4", "Public Safety", "Medium"),
        ("Garbage Collection Delay in New Colony", "Sanitation", "Medium"),
        ("Water Leakage near Market Area", "Utilities", "High"),
        ("Illegal Parking blocking Emergency Exit", "Traffic", "Critical"),
        ("Malfunctioning Traffic Signal", "Traffic", "High"),
        ("Broken Sewage Line in Old Town", "Sanitation", "Critical"),
        ("Noise Pollution from Construction Site", "Environment", "Low"),
        ("Unfair High Water Bills", "Utilities", "Medium"),
        ("Lack of Dustbins in Public Park", "Sanitation", "Low"),
        ("Stray Animal Menace in Residential Area", "Public Safety", "Medium"),
        ("Encroachment on Pedestrian Path", "Infrastructure", "High"),
    ]
    
    statuses = ["submitted", "classified", "assigned", "in_progress", "resolved"]
    cities = ["New Delhi", "Mumbai", "Bangalore", "Hyderabad", "Chennai"]
    
    complaints = []
    now = datetime.now(timezone.utc)
    
    # Get some citizen IDs if possible, otherwise use a placeholder
    citizens = await db["users"].find({"role": "citizen"}).to_list(length=5)
    citizen_ids = [c["auth0_id"] for c in citizens] if citizens else ["auth0|placeholder_citizen"]
    
    for i in range(25):
        title, category, priority = random.choice(samples)
        status = random.choice(statuses)
        city = random.choice(cities)
        created_at = now - timedelta(days=random.randint(0, 15), hours=random.randint(0, 23))
        
        complaint = {
            "title": title,
            "description": f"Detailed description for {title}. Reported in {city}.",
            "category": category,
            "status": status,
            "priority": priority.lower(),
            "location": {
                "address": f"Street {random.randint(1, 100)}, Block {chr(65 + random.randint(0, 5))}",
                "city": city,
                "state": "Sample State",
                "pincode": f"{random.randint(110001, 700001)}",
                "coordinates": {"lat": 28.6139 + random.uniform(-0.1, 0.1), "lng": 77.2090 + random.uniform(-0.1, 0.1)}
            },
            "created_by": random.choice(citizen_ids),
            "created_at": created_at,
            "images": [],
            "notes": []
        }
        
        if status == "resolved":
            complaint["feedback"] = {
                "rating": random.randint(3, 5),
                "comment": "Good resolution.",
                "created_at": created_at + timedelta(days=random.randint(1, 3))
            }
            
        complaints.append(complaint)
    
    if complaints:
        result = await db["complaints"].insert_many(complaints)
        print(f"Seeded {len(result.inserted_ids)} complaints.")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_complaints())
