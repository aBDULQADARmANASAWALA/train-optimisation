import asyncio
from app.config import get_settings
from app.main import SessionLocal, _parse_database_url
from app.models import TrainSchedule
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test():
    settings = get_settings()
    db_url = settings.database_url or _parse_database_url(settings.supabase_url)
    engine = create_engine(db_url)
    SessionClass = sessionmaker(bind=engine)
    session = SessionClass()
    
    schedules = session.query(TrainSchedule).limit(5).all()
    for s in schedules:
        print(f"Train {s.train_id}, Stop {s.stop_order}, Arrival: {s.scheduled_arrival}, Departure: {s.scheduled_departure}")

if __name__ == "__main__":
    test()
