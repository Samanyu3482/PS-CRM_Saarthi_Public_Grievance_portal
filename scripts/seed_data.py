import os
import sys
import random
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from faker import Faker
from pymongo import MongoClient
from app.core.config import settings

fake = Faker()

def seed():
    client = MongoClient(settings.MONGODB_URI)
    db = client.get_default_database()
    
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
