#!/usr/bin/env python
"""Reset system to clean state for demo."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import Settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.db_models import TrainState, TrainStatus, OptimizationLog

settings = Settings()

if settings.database_url:
    engine = create_engine(settings.database_url)
else:
    db_url = f"postgresql://{settings.supabase_db_user}:{settings.supabase_db_password}@{settings.supabase_db_host}:{settings.supabase_db_port}/{settings.supabase_db_name}"
    engine = create_engine(db_url)

Session = sessionmaker(bind=engine)
db = Session()

print("=" * 60)
print("RESETTING SYSTEM FOR CLEAN DEMO")
print("=" * 60)

try:
    # 1. Clear all train delays
    print("\n[1/2] Clearing train delays...")
    delayed_states = db.query(TrainState).filter(TrainState.accumulated_delay_minutes > 0).all()
    for state in delayed_states:
        state.accumulated_delay_minutes = 0.0
        state.status = TrainStatus.IN_TRANSIT
    db.commit()
    print(f"    ✓ Cleared {len(delayed_states)} delayed trains")
    
    # 2. Clear optimization history (to reset cumulative metrics)
    print("\n[2/2] Clearing optimization history...")
    logs_deleted = db.query(OptimizationLog).delete()
    db.commit()
    print(f"    ✓ Cleared {logs_deleted} optimization logs")
    
    print("\n" + "=" * 60)
    print("✓ SYSTEM RESET COMPLETE")
    print("=" * 60)
    print("\nMetrics after reset:")
    print("  - Active Conflicts: 0")
    print("  - Total Delay: 0 minutes")
    print("  - Delay Avoided (Cumulative): 0 minutes")
    print("  - Optimization History: Empty")
    print("\nRefresh your dashboard to see the clean state.")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()
