import os
from pymongo import MongoClient

mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
client = MongoClient(mongo_uri)
db = client['pscrm']
admin = db.users.find_one({'email': 'admin@saarthi.gov.in'})
print('Admin user document:', admin)
