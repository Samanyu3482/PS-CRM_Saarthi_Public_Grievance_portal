import os
from pymongo import MongoClient

# Load MongoDB URI from environment or settings
mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
client = MongoClient(mongo_uri)
db = client['pscrm']  # use the correct database name

admin_email = "admin@saarthi.gov.in"
admin = db.users.find_one({"email": admin_email})
if not admin:
    print(f"Admin user with email {admin_email} not found.")
else:
    updates = {}
    if admin.get("role") != "admin":
        updates["role"] = "admin"
    if not admin.get("auth0_id"):
        updates["auth0_id"] = str(admin["_id"])  # use MongoDB _id as auth0_id
    if updates:
        db.users.update_one({"_id": admin["_id"]}, {"$set": updates})
        print(f"Updated admin user with: {updates}")
    else:
        print("Admin user already has correct role and auth0_id.")
