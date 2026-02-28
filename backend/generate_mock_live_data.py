import random
import uuid
import datetime
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv(".env")

# Connect to database
engine = create_engine(os.getenv("DATABASE_URL"))

def populate_mock_live_data():
    with engine.begin() as conn:
        print("Fetching existing trains, sections, and stations...")
        
        # Get all trains
        trains_query = conn.execute(text("SELECT id FROM trains"))
        train_ids = [row[0] for row in trains_query]
        
        # Get all sections
        sections_query = conn.execute(text("SELECT id, capacity FROM sections"))
        sections = [{"id": row[0], "capacity": row[1]} for row in sections_query]
        
        # Get all stations
        stations_query = conn.execute(text("SELECT id FROM stations"))
        station_ids = [row[0] for row in stations_query]
        
        if not train_ids or not sections or not station_ids:
            print("Error: Make sure there are trains, sections, and stations in the database first!")
            return
            
        print(f"Found {len(train_ids)} trains, {len(sections)} sections, {len(station_ids)} stations.")
        
        # Clear existing states
        conn.execute(text("DELETE FROM train_states"))
        print("Cleared previous train states.")
        
        # Insert new mock states
        states_to_insert = []
        now = datetime.datetime.utcnow()
        
        # Distribute trains across different statuses
        for i, t_id in enumerate(train_ids):
            rand = random.random()
            
            # 60% of trains are IN_TRANSIT (on a section)
            if rand < 0.6:
                status = "IN_TRANSIT"
                section = random.choice(sections)
                current_section_id = section["id"]
                current_station_id = None
                
                # Assign some delay randomly
                delay = round(random.uniform(5.0, 45.0), 1) if random.random() < 0.3 else 0.0
                
            # 20% of trains are STOPPED (at a station)
            elif rand < 0.8:
                status = "STOPPED"
                current_section_id = None
                current_station_id = random.choice(station_ids)
                delay = round(random.uniform(1.0, 15.0), 1) if random.random() < 0.5 else 0.0
                
            # 10% of trains are CANCELLED
            elif rand < 0.9:
                status = "CANCELLED"
                current_section_id = None
                current_station_id = random.choice(station_ids)
                delay = 0.0
                
            # 10% of trains are SCHEDULED
            else:
                status = "SCHEDULED"
                current_section_id = None
                current_station_id = None
                delay = 0.0

            arrival = now - datetime.timedelta(minutes=random.randint(1, 30))
            departure = None if status == "STOPPED" else (now - datetime.timedelta(minutes=random.randint(1, 10)))
            
            states_to_insert.append({
                "id": str(uuid.uuid4()),
                "train_id": t_id,
                "current_section_id": current_section_id,
                "current_station_id": current_station_id,
                "status": status,
                "actual_arrival": arrival.isoformat() if current_section_id or current_station_id else None,
                "actual_departure":  departure.isoformat() if current_section_id and status == "IN_TRANSIT" else None,
                "accumulated_delay_minutes": delay,
                "last_updated": now.isoformat(),
                "created_at": now.isoformat()
            })
            
        if states_to_insert:
            query = text("""
                INSERT INTO train_states 
                (id, train_id, current_section_id, current_station_id, status, actual_arrival, actual_departure, accumulated_delay_minutes, last_updated, created_at)
                VALUES 
                (:id, :train_id, :current_section_id, :current_station_id, :status, cast(:actual_arrival as timestamp), cast(:actual_departure as timestamp), :accumulated_delay_minutes, cast(:last_updated as timestamp), cast(:created_at as timestamp))
            """)
            conn.execute(query, states_to_insert)
            
        print(f"Successfully generated 10s of live chaotic mock data!")

if __name__ == "__main__":
    try:
        populate_mock_live_data()
    except Exception as e:
        print(f"Failed to populate: {e}")
