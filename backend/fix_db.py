import os, sys
sys.path.insert(0, r'c:\Users\super\VS_CODE\MIndicatorHack\backend')
from app.models.db_models import TrainStatus
from dotenv import load_dotenv
load_dotenv(r'c:\Users\super\VS_CODE\MIndicatorHack\backend\.env')
from sqlalchemy import create_engine, text

e = create_engine(os.environ.get('DATABASE_URL'), connect_args={'connect_timeout': 10})

with e.begin() as c:
    c.execute(text("UPDATE train_state SET status = 'in_transit' WHERE UPPER(status) = 'IN_TRANSIT'"))
    c.execute(text("UPDATE train_state SET status = 'stopped' WHERE UPPER(status) = 'STOPPED'"))
    c.execute(text("UPDATE train_state SET status = 'scheduled' WHERE UPPER(status) = 'SCHEDULED'"))
    c.execute(text("UPDATE train_state SET status = 'completed' WHERE UPPER(status) = 'COMPLETED'"))
    c.execute(text("UPDATE train_state SET status = 'cancelled' WHERE UPPER(status) = 'CANCELLED'"))
    c.execute(text("UPDATE train_state SET status = 'delayed' WHERE UPPER(status) = 'DELAYED'"))
    
    # Just to be 100% sure, any stragglers:
    c.execute(text("UPDATE train_state SET status = 'in_transit' WHERE UPPER(status) = 'IN TRANSIT'"))
    c.execute(text("UPDATE train_state SET status = 'stopped' WHERE UPPER(status) = 'STATIONARY'"))

    final = c.execute(text('SELECT status FROM train_state LIMIT 5')).fetchall()
    print([r[0] for r in final])
