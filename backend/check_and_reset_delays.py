#!/usr/bin/env python
"""Check current delays and reset them."""

import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import Settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.db_models import TrainState, Train

# Load settings
settings = Settings()

# Create engine using the same config as the app
if settings.database_url:
    engine = create_engine(settings.database_url)
else:
    # Construct from Supabase settings
    db_url = f"postgresql://{settings.supabase_db_user}:{settings.supabase_db_password}@{settings.supabase_db_host}:{settings.supabase_db_port}/{settings.supabase_db_name}"
    engine = create_engine(db_url)

Session = sessionmaker(bind=engine)
db = Session()

try:
    print("=" * 60)
    print("CHECKING TRAIN DELAYS")
    print("=" * 60)
    
    # Get all train states
    states = db.query(TrainState).join(Train).all()
    print(f"\nTotal train states: {len(states)}")
    
    # Find delayed trains
    delayed = [s for s in states if s.accumulated_delay_minutes > 0]
    print(f"Trains with delays: {len(delayed)}")
    
    if delayed:
        print("\nDelayed trains:")
        for s in delayed:
            print(f"  - {s.train.train_number}: {s.accumulated_delay_minutes:.1f} min (status: {s.status.value})")
        
        print("\n" + "=" * 60)
        response = input("Reset all delays to 0? (y/n): ")
        
        if response.lower() == 'y':
            print("\nResetting delays...")
            from app.models.db_models import TrainStatus
            for s in delayed:
                s.accumulated_delay_minutes = 0.0
                s.status = TrainStatus.IN_TRANSIT
                print(f"  ✓ Reset {s.train.train_number}")
            
            db.commit()
            print(f"\n✓ Successfully reset {len(delayed)} train delays")
            print("✓ All conflicts cleared")
        else:
            print("\nReset cancelled")
    else:
        print("\n✓ No delayed trains found - system is clean")
    
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()
