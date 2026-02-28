import os, json
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv(".env")
engine = create_engine(os.getenv("DATABASE_URL"))
inspector = inspect(engine)

data = {
    "optimization_logs": [c["name"] for c in inspector.get_columns("optimization_logs")] if "optimization_logs" in inspector.get_table_names() else []
}

with open("opt_logs.json", "w") as f:
    json.dump(data, f)
