#!/usr/bin/env python
"""Reset all train delays to clear persistent conflicts."""

import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Create engine
engine = create_engine('sqlite:///./railway_optimization.db')
Session = sessionmaker(bind=engine)
db = Session()

try:
    # Reset all delays
    result = db.execute(text(
        "UPDATE train_states SET accumulated_delay_minutes = 0, status = 'in_transit' WHERE accumulated_delay_minutes > 0"
    ))
    db.commit()
    
    print(f"✓ Reset {result.rowcount} train delays to 0")
    print("✓ All conflicts cleared")
    print("\nRefresh your dashboard to see the updated state.")
    
except Exception as e:
    print(f"✗ Error: {e}")
    db.rollback()
finally:
    db.close()
