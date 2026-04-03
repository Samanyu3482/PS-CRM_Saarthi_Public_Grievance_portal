import asyncio, sys, os
sys.path.insert(0, os.getcwd())
from app.db.mongodb import connect_to_mongo, db_client

async def main():
    await connect_to_mongo()
    c = await db_client.db["complaints"].find_one()
    if c:
        print(f"ID: {c['_id']}")
    else:
        print("NO COMPLAINTS")

asyncio.run(main())
