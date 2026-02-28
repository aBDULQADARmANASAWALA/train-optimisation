import json
from sqlalchemy import create_engine, inspect
import os
from dotenv import load_dotenv

load_dotenv(".env")
engine = create_engine(os.getenv("DATABASE_URL"))
inspector = inspect(engine)

data = {
    "train_schedules": [c["name"] for c in inspector.get_columns("train_schedules")],
    "train_states": [c["name"] for c in inspector.get_columns("train_states")],
    "trains": [c["name"] for c in inspector.get_columns("trains")]
}

with open("result.json", "w") as f:
    json.dump(data, f)
