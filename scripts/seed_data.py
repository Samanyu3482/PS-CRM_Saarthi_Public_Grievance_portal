import os
import sys
import random
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from faker import Faker
from pymongo import MongoClient
from app.core.config import settings

fake = Faker()

TEST_USERS = [
    {
        "email": "citizen@example.com",
        "auth0_id": "citizen_user_123",
        "name": "John Citizen",
        "phone": "1234567890",
        "user_type": "Citizen",
    },
    {
        "email": "officer@example.com",
        "auth0_id": "officer_user_456",
        "name": "Jane Officer",
        "phone": "0987654321",
        "user_type": "Officer",
        "designation": "Municipal Commissioner",
        "ward_id": "W001",
    },
    {
        "email": "mla@example.com",
        "auth0_id": "mla_user_789",
        "name": "Ram MLA",
        "phone": "5555555555",
        "user_type": "MpMla",
        "constituency": "Central",
    },
    {
        "email": "ministry@example.com",
        "auth0_id": "ministry_user_101",
        "name": "Ministry Admin",
        "phone": "9999999999",
        "user_type": "Ministry",
        "department": "Public Grievance",
    },
]

def seed():
    client = MongoClient(settings.MONGODB_URI)
    db = client.get_default_database()
    
    # Seed test users first
    print("\nSeeding Test Users...")
    users_collection = db.users
    for user_data in TEST_USERS:
        existing = users_collection.find_one({"email": user_data["email"]})
        if existing:
            print(f"  ✓ User {user_data['email']} already exists")
        else:
            users_collection.insert_one(user_data)
            print(f"  ✓ Created {user_data['user_type']}: {user_data['email']}")
    
    print("\n📝 Test credentials for login:")
    for user in TEST_USERS:
        print(f"  - {user['email']} (role: {user['user_type']})")
    
    departments = [
        "Public Works Department (PWD)",
        "Water Supply Department",
        "Electricity Department",
        "Sanitation Department",
        "Municipal Corporation",
        "Road & Transport",
        "Health Department",
        "Police Department",
        "Education Department",
        "Revenue Department",
        "Urban Development",
        "Environment Department",
        "Housing Board"
    ]
    
    print("Clearing existing routing data...")
    db.departments.delete_many({})
    db.officers.delete_many({})
    
    print("Seeding Departments...")
    dept_docs = [{"name": dept} for dept in departments]
    db.departments.insert_many(dept_docs)
    
    print("Seeding Officers...")
    cities = ["Chandigarh", "Delhi", "Mumbai"]
    
    officers = []
    # Using 50 officers roughly distributed
    for _ in range(50):
        officer = {
            "name": fake.name(),
            "email": fake.email(),
            "phone": fake.phone_number(),
            "department": random.choice(departments),
            "city": random.choice(cities),
            "state": "India",
            "employee_id": f"EMP-{random.randint(1000,9999)}",
            "current_workload": random.randint(0, 10)
        }
        officers.append(officer)
        
    if officers:
        db.officers.insert_many(officers)
        
    print(f"Fake data creation complete! Inserted {len(departments)} departments and {len(officers)} officers.")

if __name__ == "__main__":
    seed()
