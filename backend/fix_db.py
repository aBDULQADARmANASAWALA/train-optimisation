import os
import sys

# Add backend dir to path
sys.path.append(os.path.dirname(__file__))

from app.main import init_db, SessionLocal
from app.models import TrainState

init_db()
db = SessionLocal()
states = db.query(TrainState).all()
for s in states:
    s.current_section_id = None
db.commit()
print("Fixed current_section_id!")
