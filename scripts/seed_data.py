import os
import sys
import random
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from faker import Faker
from pymongo import MongoClient
import datetime
from bson import ObjectId
from app.core.config import settings

fake = Faker('en_IN')  # Use Indian localization for names and addresses

TEST_USERS = [
    {
        "email": "citizen@example.com",
        "auth0_id": "citizen_user_123",
        "name": "John Citizen",
        "phone": "1234567890",
        "role": "citizen",
        "address": "123 Main St",
        "city": "Delhi",
        "state": "Delhi",
        "pincode": "110001",
    },
    {
        "email": "officer@example.com",
        "auth0_id": "officer_user_456",
        "name": "Jane Officer",
        "phone": "0987654321",
        "role": "officer",
        "designation": "Municipal Commissioner",
        "department": "Public Works",
        "city": "Delhi",
        "employee_id": "OFF-001",
    },
    {
        "email": "mla@example.com",
        "auth0_id": "mla_user_789",
        "name": "Ram MLA",
        "phone": "5555555555",
        "role": "mp_mla",
        "constituency": "Central",
        "state": "Delhi",
        "party_name": "Independent",
    },
    {
        "email": "admin@saarthi.gov.in",
        "auth0_id": "admin_user_999",
        "name": "System Admin",
        "phone": "8888888888",
        "role": "admin",
    },
]


def seed():
    client = MongoClient(settings.MONGODB_URI)
    # Match the fallback behavior in the app
    db = client.get_default_database("pscrm") 
    
    # Seed test users first
    print("\nSeeding Test Users...")
    users_collection = db.users
    for user_data in TEST_USERS:
        existing = users_collection.find_one({"email": user_data["email"]})
        if existing:
            print(f"  ✓ User {user_data['email']} already exists")
        else:
            users_collection.insert_one(user_data)
            print(f"  ✓ Created {user_data['role']}: {user_data['email']}")
    
    print("\n📝 Test credentials for login:")
    for user in TEST_USERS:
        print(f"  - {user['email']} (role: {user['role']})")
    
    ministries_data = {
        "Ministry of Finance": {
            "Department of Revenue": ["Income Tax Department", "CBIC (Customs & GST)"],
            "Department of Financial Services": ["Public Sector Banks", "Insurance Companies", "PFRDA (Pension)"]
        },
        "Ministry of Railways": {
            "Railway Board": ["Ticket Booking Issues", "Refund Issues", "Passenger Complaints"]
        },
        "Ministry of Petroleum and Natural Gas": {
            "Oil Marketing Companies": ["LPG Subsidy", "Gas Delivery", "Fuel Quality"]
        },
        "Ministry of Labour and Employment": {
            "EPFO": ["PF Withdrawal", "PF Transfer", "UAN Issues"],
            "ESIC": ["ESI Claims", "Hospital Services"]
        },
        "Ministry of Housing and Urban Affairs": {
            "Urban Bodies": ["CPWD", "DDA", "Municipal Services"]
        },
        "Ministry of Power": {
            "Electricity Services": ["Power Cuts", "Billing Issues"]
        },
        "Ministry of Communications": {
            "Telecom": ["Call Drops", "Network Issues"],
            "Postal Services": ["Speed Post Delay", "Parcel Issues"]
        }
    }
    
    print("Clearing existing routing and complaint data...")
    db.departments.delete_many({})
    db.officers.delete_many({})
    db.complaints.delete_many({})
    db.notifications.delete_many({})
    
    print("Seeding Departments...")
    dept_docs = []
    officer_assignments = []
    
    for min_name, depts in ministries_data.items():
        for dept_name, subs in depts.items():
            dept_docs.append({
                "ministry": min_name,
                "department": dept_name,
                "sub_departments": subs
            })
            for sub in subs:
                officer_assignments.append({
                    "ministry": min_name,
                    "department": dept_name,
                    "sub_department": sub
                })
                
    db.departments.insert_many(dept_docs)
    
    print("Seeding Officers (Delhi Focused)...")
    cities = ["New Delhi", "South Delhi", "North Delhi", "East Delhi", "West Delhi", "Central Delhi"]
    
    officers = []
    officers_dict = {}  # Keep track by assignment tuple for assigning complaints later
    
    for _ in range(120):
        assignment = random.choice(officer_assignments)
        officer = {
            "_id": ObjectId(),
            "name": fake.name(),
            "email": fake.email(),
            "phone": fake.phone_number(),
            "ministry": assignment["ministry"],
            "department": assignment["department"],
            "sub_department": assignment["sub_department"],
            "city": random.choice(cities),
            "state": "Delhi",
            "employee_id": f"EMP-{random.randint(1000,9999)}",
            "current_workload": 0 # Will map logically below
        }
        officers.append(officer)
        key = (assignment["ministry"], assignment["department"])
        if key not in officers_dict:
            officers_dict[key] = []
        officers_dict[key].append(officer)
        
    if officers:
        db.officers.insert_many(officers)
        
    print(f"Fake routing data creation complete. Departments: {len(dept_docs)}, Officers: {len(officers)}")

    print("Generating Large Volume of Complaints for Delhi User...")
    
    AUTH0_ID = "OOF13pFYmSsngRRLd1I8piKwpeHnUQua@clients"
    
    statuses = ["submitted", "assigned", "in_progress", "resolved", "closed"]
    priorities = ["low", "medium", "high", "critical"]
    delhi_areas = ["Chandni Chowk", "Connaught Place", "Hauz Khas", "Karol Bagh", "Lajpat Nagar", "Saket", "Vasant Kunj", "Dwarka", "Rohini"]
    
    complaints = []
    notifications = []
    
    num_complaints = 300
    
    for i in range(num_complaints):
        status = random.choice(statuses)
        assignment = random.choice(officer_assignments)
        
        # Pick an officer matching the department
        key = (assignment["ministry"], assignment["department"])
        assigned_officer = random.choice(officers_dict[key]) if key in officers_dict else None
        
        assigned_to = str(assigned_officer["_id"]) if assigned_officer and status in ["assigned", "in_progress", "resolved", "closed"] else None
        
        created_date = fake.date_time_between(start_date="-30d", end_date="now")
        
        complaint_id = ObjectId()
        
        # Build Feedback if resolved
        feedback = None
        if status in ["resolved", "closed"] and random.random() > 0.3:
            feedback = {
                "rating": random.randint(1, 5),
                "comment": fake.sentence(),
                "created_at": created_date + datetime.timedelta(days=random.randint(1, 5))
            }
            
        # Build Officer Notes
        notes = []
        if assigned_to and random.random() > 0.4:
            notes.append({
                "user_id": assigned_to,
                "text": fake.sentence(),
                "created_at": created_date + datetime.timedelta(days=1)
            })
            
        location = {
            "address": fake.street_address(),
            "city": random.choice(delhi_areas),
            "state": "Delhi",
            "pincode": f"1100{random.randint(10, 99)}",
            "coordinates": {"lat": 28.6139 + random.uniform(-0.1, 0.1), "lng": 77.2090 + random.uniform(-0.1, 0.1)}
        }
        
        complaints.append({
            "_id": complaint_id,
            "title": f"{assignment['sub_department']} Issue at {location['city']}",
            "description": fake.paragraph(nb_sentences=3),
            "category": None,
            "location": location,
            "images": [f"https://picsum.photos/seed/{random.randint(1,1000)}/400/300"] if random.random() > 0.5 else [],
            "created_by": AUTH0_ID,
            "status": status,
            "priority": random.choice(priorities),
            "assigned_to": assigned_to,
            "ministry": assignment["ministry"],
            "department": assignment["department"],
            "sub_department": assignment["sub_department"],
            "duplicate_of": None,
            "sentiment_score": round(random.uniform(-1.0, 1.0), 2),
            "sla_deadline": created_date + datetime.timedelta(days=7),
            "feedback": feedback,
            "notes": notes,
            "created_at": created_date
        })
        
        # Create a notification for this complaint
        if random.random() > 0.2:
            notifications.append({
                "user_id": AUTH0_ID,
                "message": f"Update on your complaint regarding '{assignment['sub_department']}': Status is now {status}.",
                "is_read": random.choice([True, False]),
                "created_at": created_date + datetime.timedelta(hours=random.randint(1, 48))
            })
            
        # Update officer workload locally so it makes sense realistically
        if assigned_to and status in ["assigned", "in_progress"]:
            assigned_officer["current_workload"] += 1

    if complaints:
        db.complaints.insert_many(complaints)
    if notifications:
        db.notifications.insert_many(notifications)
        
    print(f"Data Generation Successful! Inserted {len(complaints)} complaints and {len(notifications)} notifications for auth0 user {AUTH0_ID} in Delhi.")

if __name__ == "__main__":
    seed()
