import asyncio
import os
import random
import bcrypt
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete
from dotenv import load_dotenv

# Ensure PYTHONPATH includes current directory
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db.database import engine, Base, AsyncSessionLocal
from app.db.models import UserDB, ComplaintDB, DepartmentDB, OfficerDB

# CM Details
CM_EMAIL = "cm.delhi@gov.in"
CM_NAME = "Chief Minister of Delhi"
CM_UID = "delhi_cm_uid"
CM_PWD = "123456"

# Delhi District names
DELHI_DISTRICTS = [
    "New Delhi",
    "Central Delhi",
    "South Delhi",
    "North Delhi",
    "West Delhi",
    "East Delhi",
    "Dwarka",
    "Shahdara",
    "Rohini",
    "South West Delhi"
]

# Delhi-specific departments and complaints list
DELHI_COMPLAINTS = [
    # Delhi Jal Board (Water/Sewage)
    ("Contaminated tap water supply in Dwarka Sector 12", "The tap water received in our residential block has been yellowish and muddy for the past 4 days. Strong odor. DJB needs to inspect pipelines.", "Delhi Jal Board", "Water Supply", "critical"),
    ("Main sewage pipeline overflow near Central Market Lajpat Nagar", "Sewage water is overflowing from a broken manhole, flooding the main pedestrian path. Bad smell and hygiene hazard.", "Delhi Jal Board", "Sewage & Drainage", "high"),
    ("No water supply for 48 hours in Rohini Sector 8", "Entire street has received no water supply. The local DJB booster pump is malfunctioning. Urgent resolution needed.", "Delhi Jal Board", "Water Supply", "critical"),
    ("Low water pressure in Shakurpur area", "Water pressure is so low that it does not reach the first floor. Working professionals and elderly are suffering.", "Delhi Jal Board", "Water Supply", "low"),
    
    # Public Works Department (Roads/Bridges)
    ("Dangerous potholes on Outer Ring Road near IIT Flyover", "Multiple large potholes have formed on the high-speed lane right after the flyover. Vehicles are swerving dangerously.", "Public Works Department", "Road Repair", "critical"),
    ("Waterlogging under Pul Prahladpur underpass", "Even after light rain, the underpass is flooded with 3 feet of water. Traffic is completely stalled. Pump is not operational.", "Public Works Department", "Sewage & Drainage", "critical"),
    ("Damaged footpath tiles near Connaught Place Outer Circle", "Broken and missing tiles on the pavement make it extremely difficult for pedestrians and visually impaired citizens to walk.", "Public Works Department", "Public Safety", "medium"),
    ("Fallen tree blocking lane on Aurobindo Marg", "A heavy branch has fallen, blocking one of the active lanes. Traffic congestion building up.", "Public Works Department", "Road Repair", "medium"),

    # Municipal Corporation of Delhi (Garbage/Encroachment/Parks)
    ("Uncontrolled garbage dumping near MCD Primary School, Shahdara", "A massive heap of garbage has accumulated outside the school gates. MCD trucks haven't cleared it for 6 days. Stray dogs/bulls gather here.", "Municipal Corporation of Delhi", "Garbage Cleaning", "high"),
    ("Street vendors encroaching footpaths in Karol Bagh Market", "Illegal stalls have blocked all pedestrian paths, forcing people to walk on the busy road. Heavy traffic jams.", "Municipal Corporation of Delhi", "Encroachments", "medium"),
    ("Dilapidated conditions of MCD Park in Sector 4, Dwarka", "The park benches are broken, high grass is uncut, and open gym equipment is rusted. Dangerous for children.", "Municipal Corporation of Delhi", "Public Safety", "medium"),
    ("Stray dog menace near pocket-2 park, Rajouri Garden", "Pack of 10-12 stray dogs has become aggressive. Three bites reported in the last week. MCD veterinary department needs to act.", "Municipal Corporation of Delhi", "Public Safety", "high"),

    # Delhi Police (Public Safety/Traffic)
    ("Dark stretch with zero streetlights near Sigra border road", "The entire 500m stretch is completely dark due to non-functional streetlights. Multiple instances of chain snatching reported.", "Delhi Police", "Public Safety", "high"),
    ("Reckless driving and stunt biking on Rajpath late night", "Group of bikers perform dangerous stunts every Sunday night around 11 PM. Major risk to regular commuters.", "Delhi Police", "Public Safety", "medium"),
    ("Unlawful parking blocking emergency ambulance gate at LNJP Hospital", "Private cars and auto-rickshaws are permanently parked in front of the emergency gates. Security guards are unresponsive.", "Delhi Police", "Public Safety", "critical"),

    # Delhi Transport Corporation (Public Transport)
    ("Irregular DTC bus frequency on Route 502", "Bus frequency has dropped to 1 bus per hour instead of 15 minutes. Heavy crowds at Saket terminal.", "Delhi Transport Corporation", "Public Transport", "medium"),
    ("DTC bus driver refusing to stop at designated bus stop near ITO", "Bus number DL1PD 4322 sped past the bus stop despite passengers waving. This is a recurring issue during peak hours.", "Delhi Transport Corporation", "Public Transport", "low"),
    ("AC not working in DTC Electric Bus", "The air conditioning in electric bus DL1PD 9876 is broken. Temperature inside is unbearable. Please repair.", "Delhi Transport Corporation", "Public Transport", "low"),

    # Health Department (Hospitals/Clinics)
    ("Long waiting queues and lack of wheel chairs at GTB Hospital", "My elderly mother had to wait 3 hours for a basic checkup. Only 2 working wheelchairs in the entire OPD block.", "Health Department", "Government Hospitals", "high"),
    ("Medicines out of stock at Mohalla Clinic, Govindpuri", "Essential medicines for diabetes and blood pressure are unavailable for the last 3 weeks. Patients forced to buy from private stores.", "Health Department", "Government Hospitals", "medium"),

    # Education Department (Schools)
    ("Broken desks and non-functional fans in Class 8, Sarvodaya Kanya Vidyalaya", "In this extreme summer heat, 2 ceiling fans in class 8B are not working. Children are falling sick.", "Education Department", "Government Schools", "medium"),
    ("Drinking water cooler out of order in Govt Boys Senior Secondary School, Rohini", "The drinking water filter plant is broken, forcing kids to drink warm, unfiltered tap water.", "Education Department", "Government Schools", "high")
]

STATUS_CHOICES = ["submitted", "classified", "assigned", "in_progress", "resolved", "closed"]
PRIORITIES = ["low", "medium", "high", "critical"]

async def seed_data():
    load_dotenv()
    
    # 1. Initialize tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[INFO] PostgreSQL tables initialized.")

    session = AsyncSessionLocal()

    try:
        # Clean up existing Delhi data to prevent duplicates
        await session.execute(delete(ComplaintDB).where(ComplaintDB.ministry == "Delhi State Government"))
        await session.execute(delete(UserDB).where(UserDB.email == CM_EMAIL))
        await session.execute(delete(OfficerDB))
        await session.execute(delete(DepartmentDB))
        await session.commit()
        print("[INFO] Old Delhi data cleaned.")

        # 2. Seed Departments
        departments_to_seed = {
            "Delhi Jal Board": ["Water Supply", "Sewage & Drainage"],
            "Public Works Department": ["Road Repair", "Bridge Maintenance", "Public Safety"],
            "Municipal Corporation of Delhi": ["Garbage Cleaning", "Encroachments", "Public Safety", "Parks"],
            "Delhi Police": ["Public Safety", "Traffic Control"],
            "Delhi Transport Corporation": ["Public Transport", "Bus Maintenance"],
            "Health Department": ["Government Hospitals", "Mohalla Clinics"],
            "Education Department": ["Government Schools", "Vocational Training"]
        }

        db_deps = []
        for dept_name, sub_deps in departments_to_seed.items():
            db_dep = DepartmentDB(
                id=str(uuid.uuid4()),
                ministry="Delhi State Government",
                department=dept_name,
                sub_departments=sub_deps
            )
            session.add(db_dep)
            db_deps.append(db_dep)
        await session.commit()
        print("[SUCCESS] Seeded Delhi departments.")

        # 3. Seed Officers (one officer per department per district to ensure successful routing)
        officers_to_seed = []
        for district in DELHI_DISTRICTS:
            for dept_name in departments_to_seed.keys():
                employee_num = random.randint(1000, 9999)
                dept_code = "".join([w[0] for w in dept_name.split() if w.istitle()])
                officer_email = f"officer.{dept_code.lower()}.{employee_num}@delhi.gov.in"
                
                db_officer = OfficerDB(
                    id=str(uuid.uuid4()),
                    name=f"Officer {dept_name} ({district})",
                    email=officer_email,
                    phone=f"+919811{random.randint(100000, 999999)}",
                    ministry="Delhi State Government",
                    department=dept_name,
                    sub_department=departments_to_seed[dept_name][0],
                    city=district,
                    state="Delhi",
                    employee_id=f"DEL-{dept_code}-{employee_num}",
                    current_workload=0
                )
                session.add(db_officer)
                officers_to_seed.append(db_officer)
                
                # Also create a user record for each official so they can log in
                hashed_pwd = bcrypt.hashpw("123456".encode(), bcrypt.gensalt()).decode()
                db_officer_user = UserDB(
                    id=db_officer.id,
                    firebase_uid=f"officer_uid_{district.lower().replace(' ', '_')}_{dept_code.lower()}",
                    name=db_officer.name,
                    email=officer_email,
                    phone=db_officer.phone,
                    role="officer",
                    password_hash=hashed_pwd,
                    department=db_officer.department,
                    city=db_officer.city,
                    state=db_officer.state,
                    employee_id=db_officer.employee_id
                )
                session.add(db_officer_user)
                
        await session.commit()
        print(f"[SUCCESS] Seeded {len(officers_to_seed)} Delhi Officers and User credentials.")

        # 4. Create Delhi CM User
        hashed_pwd = bcrypt.hashpw(CM_PWD.encode(), bcrypt.gensalt()).decode()
        cm_user = UserDB(
            id=str(uuid.uuid4()),
            firebase_uid=CM_UID,
            name=CM_NAME,
            email=CM_EMAIL,
            phone="+911123392020",
            role="delhi_cm",
            password_hash=hashed_pwd,
            employee_id="CM-DELHI-001",
            state="Delhi"
        )
        session.add(cm_user)
        await session.commit()
        print(f"[SUCCESS] Seeded Chief Minister user: {CM_EMAIL}")

        # 5. Generate 55 complaints
        now = datetime.now(timezone.utc)
        
        # We need a citizen UID to assign as creator
        citizen_uid = "citizen_delhi_uid"
        
        # Create a mock citizen user first
        db_citizen = UserDB(
            id=str(uuid.uuid4()),
            firebase_uid=citizen_uid,
            name="Rahul Sharma",
            email="rahul.sharma@example.com",
            phone="+919999888877",
            role="citizen",
            address="Pocket B, Sector 4",
            city="Dwarka",
            state="Delhi",
            pincode="110075"
        )
        session.add(db_citizen)
        await session.commit()

        # Build list of seeded officers by (dept, city) for assignment lookup
        officer_lookup = {(o.department, o.city): o for o in officers_to_seed}

        for i in range(55):
            title, desc, dept, category, base_priority = random.choice(DELHI_COMPLAINTS)
            title_unique = f"[{i+1}] {title}"
            district = random.choice(DELHI_DISTRICTS)
            
            status = random.choice(STATUS_CHOICES)
            priority = random.choice(PRIORITIES) if random.random() > 0.6 else base_priority
            
            days_ago = random.randint(0, 30)
            hours_ago = random.randint(0, 23)
            created_at = now - timedelta(days=days_ago, hours=hours_ago)
            
            lat = 28.5 + random.uniform(0.05, 0.22)
            lng = 77.0 + random.uniform(0.05, 0.25)
            
            location_data = {
                "address": f"Street No. {random.randint(1,24)}, Near Metro Station, Block {random.choice(['A','B','C','D','H','K'])}, {district}",
                "city": district,
                "state": "Delhi",
                "pincode": f"1100{random.randint(10,99)}",
                "coordinates": {
                    "lat": lat,
                    "lng": lng
                }
            }

            assigned_to = None
            if status in ("assigned", "in_progress", "resolved", "closed"):
                matched_officer = officer_lookup.get((dept, district))
                if matched_officer:
                    assigned_to = matched_officer.id
                    # Increment workload
                    matched_officer.current_workload += 1
                    session.add(matched_officer)

            # SLA deadline
            sla_deadline = None
            if status != "submitted":
                sla_deadline = created_at + timedelta(days=random.choice([7, 10, 14]))

            # Feedback
            feedback = None
            if status in ("resolved", "closed"):
                rating = random.choice([4, 5]) if priority == "low" else random.choice([1, 2, 3, 4, 5])
                comments = [
                    "Good prompt response from DJB team.",
                    "Thank you CM office, road got repaired after a long time.",
                    "Garbage was cleared but the odor remains. Adequate sweepers needed.",
                    "Resolution was very slow, took almost 2 weeks.",
                    "Satisfactory outcome, the park is now safe for kids."
                ]
                feedback = {
                    "rating": rating,
                    "comment": random.choice(comments),
                    "created_at": (created_at + timedelta(days=random.randint(2, 6))).isoformat()
                }

            # Generate dummy 384 dimensional embedding
            dummy_embedding = [random.uniform(-0.1, 0.1) for _ in range(384)]

            db_complaint = ComplaintDB(
                id=str(uuid.uuid4()),
                title=title_unique,
                description=desc,
                category=category,
                location=location_data,
                images=[],
                created_by=citizen_uid,
                status=status,
                priority=priority,
                assigned_to=assigned_to,
                ministry="Delhi State Government",
                department=dept,
                sub_department=f"{category} Division",
                duplicate_of=None,
                sentiment_score=None,
                sla_deadline=sla_deadline,
                feedback=feedback,
                embedding=dummy_embedding,
                notes=[],
                is_spam=False,
                spam_matched_on=[],
                spam_reason=None,
                created_at=created_at
            )
            session.add(db_complaint)

        await session.commit()
        print("[SUCCESS] Successfully seeded 55 Delhi grievances into PostgreSQL.")

    except Exception as e:
        await session.rollback()
        print(f"[ERROR] Seeding failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await session.close()
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_data())
