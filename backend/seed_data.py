"""
seed_data.py
============
One-shot Supabase seeder for the Mindicator hackathon demo.

Run from backend directory (with venv activated):
    python seed_data.py

What it creates
---------------
  • 8 stations  (Mumbai-Pune corridor + cross-links)
  • 10 sections (directed track segments with real headway / capacity)
  • 6 trains    (mixed express + passenger + freight with priority weights)
  • train_schedules — full timetable for each train (3-5 stops each)
  • train_routes    — section sequence per train
  • train_state     — initial live state (IN_TRANSIT / SCHEDULED / DELAYED)
  • section_occupancy / platform_occupancy — starting occupancy
  • historical_operational_data — 250 realistic rows (ML training data)

Safe to run multiple times — uses INSERT ... ON CONFLICT DO NOTHING.
"""

import os
import sys
import random
import uuid
from datetime import datetime, timedelta

# ── Load .env so DATABASE_URL / SUPABASE_* are available ─────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional

from sqlalchemy import create_engine, text

# ── Database URL (same logic as main.py) ─────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
if not DATABASE_URL:
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "")
    if not supabase_url:
        print("ERROR: Set DATABASE_URL or SUPABASE_URL in your .env file.")
        sys.exit(1)
    # Construct pgbouncer-style URL from Supabase project URL
    project_id = supabase_url.replace("https://", "").replace(".supabase.co", "")
    db_password = os.environ.get("SUPABASE_DB_PASSWORD", "")
    DATABASE_URL = (
        f"postgresql://postgres.{project_id}:{db_password}"
        f"@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
    )

print(f"Connecting to: {DATABASE_URL[:60]}...")
engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 10})

# ── Helpers ───────────────────────────────────────────────────────────────────
def uid():
    return str(uuid.uuid4())

def mins_from_now(m: int) -> str:
    return (datetime.utcnow() + timedelta(minutes=m)).isoformat()

def rand_delay(max_d: int = 20) -> int:
    """Generate realistic skewed delay — most trains slightly late."""
    return int(random.choices(
        population=range(0, max_d + 1),
        weights=[10] + [6] * 5 + [3] * 5 + [1] * 10,
        k=1,
    )[0])

# ── Seed Data Definitions ─────────────────────────────────────────────────────

STATIONS = [
    # (id, station_code, name, zone, division, lat, lon, total_platforms)
    ("s1", "CSMT", "Mumbai CSMT",       "CR", "Mumbai",  18.9400, 72.8350, 18),
    ("s2", "DR",   "Dadar",             "CR", "Mumbai",  19.0181, 72.8414,  8),
    ("s3", "TNA",  "Thane",             "CR", "Mumbai",  19.1815, 72.9619,  6),
    ("s4", "KYN",  "Kalyan Junction",   "CR", "Mumbai",  19.2403, 73.1305,  8),
    ("s5", "IGP",  "Igatpuri",          "CR", "Nashik",  19.6977, 73.5595,  4),
    ("s6", "NK",   "Nashik Road",       "CR", "Nashik",  19.9975, 73.7898,  4),
    ("s7", "DD",   "Devlali",           "CR", "Nashik",  19.9449, 73.8400,  3),
    ("s8", "MMR",  "Manmad Junction",   "CR", "Nashik",  20.2527, 74.4389,  6),
]

# Directed sections: (id, from_key, to_key, dist_km, travel_min, capacity, headway_min)
SECTIONS = [
    ("sec1",  "s1", "s2",  6,   8,  4,  3),   # CSMT → Dadar
    ("sec2",  "s2", "s3", 17,  20,  4,  3),   # Dadar → Thane
    ("sec3",  "s3", "s4", 16,  18,  3,  4),   # Thane → Kalyan
    ("sec4",  "s4", "s5", 59,  65,  2,  8),   # Kalyan → Igatpuri (ghat section, tight)
    ("sec5",  "s5", "s6", 64,  55,  2,  8),   # Igatpuri → Nashik Road
    ("sec6",  "s6", "s7",  6,   6,  3,  4),   # Nashik Road → Devlali
    ("sec7",  "s7", "s8", 62,  58,  2,  8),   # Devlali → Manmad
    # Reverse (bidirectional)
    ("sec8",  "s2", "s1",  6,   8,  4,  3),
    ("sec9",  "s3", "s2", 17,  20,  4,  3),
    ("sec10", "s4", "s3", 16,  18,  3,  4),
]

# (id, train_number, train_type, priority_weight, max_speed, rake_length)
TRAINS = [
    ("t1", "12125", "SuperFast_Express", 10, 110, 22),  # highest priority
    ("t2", "12701", "Rajdhani_Express",  9,  130, 20),
    ("t3", "17412", "Mail_Express",      6,   90, 18),
    ("t4", "51031", "Passenger",         3,   70, 14),
    ("t5", "GDSF1", "Goods_Freight",     1,   60, 40),
    ("t6", "12107", "Duronto_Express",   8,  120, 20),
]

# Schedules: (train_key, [(station_key, stop_order, arr_offset_min, dep_offset_min)])
# Offsets relative to "now"
SCHEDULES = {
    "t1": [("s1",1,-10,-5), ("s2",2,5,8),  ("s3",3,30,33), ("s4",4,52,55),  ("s5",5,120,123)],
    "t2": [("s1",1,-5, 0),  ("s2",2,9,12), ("s3",3,35,38), ("s4",4,55,58),  ("s8",5,180,183)],
    "t3": [("s2",1,-15,-10),("s3",2,12,16),("s4",3,35,40), ("s5",4,108,113),("s6",5,170,175)],
    "t4": [("s1",1,0,  5),  ("s2",2,14,20),("s3",3,45,55), ("s4",4,80,95)],
    "t5": [("s4",1,10, 20), ("s5",2,90,110),("s6",3,165,180),("s7",4,190,200),("s8",5,260,270)],
    "t6": [("s1",1,-20,-15),("s2",2,0,  3), ("s3",3,24,27), ("s4",4,45,48),  ("s5",5,115,118)],
}

# Train routes: (train_key, [(section_key, seq)])
ROUTES = {
    "t1": [("sec1",1), ("sec2",2), ("sec3",3), ("sec4",4)],
    "t2": [("sec1",1), ("sec2",2), ("sec3",3), ("sec4",4), ("sec5",5), ("sec6",6), ("sec7",7)],
    "t3": [("sec2",1), ("sec3",2), ("sec4",3), ("sec5",4)],
    "t4": [("sec1",1), ("sec2",2), ("sec3",3)],
    "t5": [("sec4",1), ("sec5",2), ("sec6",3), ("sec7",4)],
    "t6": [("sec1",1), ("sec2",2), ("sec3",3), ("sec4",4)],
}

# Initial train states: (train_key, current_section_key, current_station_key, status, delay_min)
TRAIN_STATES = [
    ("t1", "sec2", "s2", "in_transit", 3),
    ("t2", "sec1", "s1", "in_transit", 0),
    ("t3",  None,  "s3", "stopped",    8),
    ("t4", "sec1",  None,"in_transit", 0),
    ("t5", "sec4",  None,"in_transit", 12),
    ("t6",  None,  "s1", "scheduled",  0),
]

# ── Insert Functions ──────────────────────────────────────────────────────────

def run_seed():
    sid   = {s[0]: uid() for s in STATIONS}
    secid = {s[0]: uid() for s in SECTIONS}
    tid   = {t[0]: uid() for t in TRAINS}
    sec_map  = {s[0]: s for s in SECTIONS}   # key → tuple
    stat_map = {s[0]: s for s in STATIONS}

    with engine.begin() as conn:

        # ── Stations ─────────────────────────────────────────────────────────
        print("Seeding stations...")
        for s in STATIONS:
            conn.execute(text("""
                INSERT INTO stations
                    (id, station_code, name, zone, division, latitude, longitude, total_platforms)
                VALUES
                    (:id,:code,:name,:zone,:div,:lat,:lon,:plat)
                ON CONFLICT (station_code) DO NOTHING
            """), dict(id=sid[s[0]], code=s[1], name=s[2], zone=s[3],
                       div=s[4], lat=s[5], lon=s[6], plat=s[7]))

        # ── Sections ─────────────────────────────────────────────────────────
        print("Seeding sections...")
        for s in SECTIONS:
            _, fk, tk, dist, travel, cap, hw = s
            conn.execute(text("""
                INSERT INTO sections
                    (id, from_station_id, to_station_id, distance_km,
                     travel_time_minutes, capacity, headway_minutes,
                     signalling_type, max_speed_kmph, is_bidirectional)
                VALUES
                    (:id,:from_id,:to_id,:dist,
                     :travel,:cap,:hw,
                     'automatic',110,true)
                ON CONFLICT (id) DO NOTHING
            """), dict(id=secid[s[0]], from_id=sid[fk], to_id=sid[tk],
                       dist=dist, travel=travel, cap=cap, hw=hw))

        # ── Trains ───────────────────────────────────────────────────────────
        print("Seeding trains...")
        for t in TRAINS:
            conn.execute(text("""
                INSERT INTO trains
                    (id, train_number, train_type, priority_weight, max_speed_kmph, rake_length)
                VALUES
                    (:id,:num,:ttype,:pw,:spd,:rake)
                ON CONFLICT (train_number) DO NOTHING
            """), dict(id=tid[t[0]], num=t[1], ttype=t[2],
                       pw=t[3], spd=t[4], rake=t[5]))

        # ── Train Schedules ───────────────────────────────────────────────────
        print("Seeding train_schedules...")
        sched_id_map = {}
        for tkey, stops in SCHEDULES.items():
            for stkey, order, arr_off, dep_off in stops:
                row_id = uid()
                sched_id_map[(tkey, stkey, order)] = row_id
                conn.execute(text("""
                    INSERT INTO train_schedules
                        (id, train_id, station_id, scheduled_arrival,
                         scheduled_departure, stop_order)
                    VALUES
                        (:id,:tid,:sid,:arr,:dep,:ord)
                    ON CONFLICT (id) DO NOTHING
                """), dict(id=row_id, tid=tid[tkey], sid=sid[stkey],
                           arr=mins_from_now(arr_off),
                           dep=mins_from_now(dep_off),
                           ord=order))

        # ── Train Routes ─────────────────────────────────────────────────────
        print("Seeding train_routes...")
        for tkey, seqs in ROUTES.items():
            for seckey, seq in seqs:
                conn.execute(text("""
                    INSERT INTO train_routes
                        (id, train_id, section_id, sequence_order)
                    VALUES
                        (:id,:tid,:secid,:seq)
                    ON CONFLICT (id) DO NOTHING
                """), dict(id=uid(), tid=tid[tkey],
                           secid=secid[seckey], seq=seq))

        # ── Train State ───────────────────────────────────────────────────────
        print("Seeding train_state...")
        for tkey, seckey, stkey, status, delay in TRAIN_STATES:
            conn.execute(text("""
                INSERT INTO train_state
                    (train_id, current_section_id, current_station_id,
                     status, actual_arrival, actual_departure,
                     accumulated_delay_minutes, last_updated)
                VALUES
                    (:tid,:secid,:stid,:stat,
                     NOW() - INTERVAL '5 minutes',
                     NOW(),
                     :delay, NOW())
                ON CONFLICT (train_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    accumulated_delay_minutes = EXCLUDED.accumulated_delay_minutes,
                    last_updated = NOW()
            """), dict(
                tid=tid[tkey],
                secid=secid[seckey] if seckey else None,
                stid=sid[stkey]  if stkey  else None,
                stat=status,
                delay=delay,
            ))

        # ── Section Occupancy ─────────────────────────────────────────────────
        print("Seeding section_occupancy...")
        # t1 on sec2, t4 on sec1, t5 on sec4
        for tkey, seckey in [("t1","sec2"),("t4","sec1"),("t5","sec4")]:
            _, fk, tk, _, travel, _, _ = sec_map[seckey]
            conn.execute(text("""
                INSERT INTO section_occupancy
                    (section_id, train_id, entry_time, expected_exit_time)
                VALUES
                    (:secid,:tid, NOW() - INTERVAL '3 minutes',
                                 NOW() + MAKE_INTERVAL(mins => :travel))
                ON CONFLICT (section_id, train_id) DO NOTHING
            """), dict(secid=secid[seckey], tid=tid[tkey], travel=travel))

        # ── Platform Occupancy ────────────────────────────────────────────────
        print("Seeding platform_occupancy...")
        for tkey, stkey in [("t3","s3"),("t6","s1")]:
            # We need a platform id — use first platform of that station
            # Since platforms table may be empty we'll just try and ignore errors
            try:
                plat_result = conn.execute(text(
                    "SELECT id FROM platforms WHERE station_id=:sid LIMIT 1"
                ), dict(sid=sid[stkey])).fetchone()
                if plat_result:
                    conn.execute(text("""
                        INSERT INTO platform_occupancy
                            (platform_id, train_id, arrival_time, departure_time)
                        VALUES
                            (:pid,:tid, NOW() - INTERVAL '10 minutes',
                                        NOW() + INTERVAL '5 minutes')
                        ON CONFLICT (platform_id, train_id) DO NOTHING
                    """), dict(pid=plat_result[0], tid=tid[tkey]))
            except Exception:
                pass  # platforms table may not have rows yet

        # ── Historical Operational Data (250 rows = ML training corpus) ───────
        print("Seeding historical_operational_data (250 rows)...")
        section_keys = list(secid.keys())
        train_keys   = list(tid.keys())

        for i in range(250):
            tkey   = random.choice(train_keys)
            seckey = random.choice(section_keys)

            # Time of day: peak hours (7-9, 17-20) skewed heavy
            hour = random.choices(
                population=list(range(24)),
                weights=[1,1,1,1,1,1,2, 8,8,4, 3,3,3,3, 3,3, 5,8,8,6, 3,2,1,1],
                k=1,
            )[0]
            minute = random.randint(0, 59)
            time_of_day = hour * 60 + minute

            # Section load: higher during peak
            is_peak = hour in range(7,10) or hour in range(17,21)
            sec_cap = sec_map[seckey][5]
            section_load = random.randint(
                1 if is_peak else 0,
                sec_cap if is_peak else max(1, sec_cap - 1),
            )

            # Departure delay: freight and low-priority trains delay more
            train_priority = next(t[3] for t in TRAINS if t[0] == tkey)
            max_dep_delay  = 30 if train_priority <= 3 else 15 if train_priority <= 6 else 8
            departure_delay = rand_delay(max_dep_delay)

            # Arrival delay: correlated with departure delay + section load
            base_arr_delay = departure_delay + (5 if section_load >= sec_cap else 0)
            arrival_delay  = max(0, base_arr_delay + random.randint(-2, 4))

            # Congestion: true when section at or above capacity+headway stress
            congestion = section_load >= sec_cap or (section_load >= sec_cap - 1 and is_peak)

            # Spread records over past 30 days
            days_ago = random.randint(0, 30)
            hours_ago = random.randint(0, 23)
            created = datetime.utcnow() - timedelta(days=days_ago, hours=hours_ago)

            conn.execute(text("""
                INSERT INTO historical_operational_data
                    (id, train_id, section_id, departure_delay, arrival_delay,
                     section_load, time_of_day, congestion_flag, created_at)
                VALUES
                    (:id,:tid,:secid,:ddel,:adel,:sload,:tod,:cong,:created)
                ON CONFLICT (id) DO NOTHING
            """), dict(
                id=uid(),
                tid=tid[tkey],
                secid=secid[seckey],
                ddel=departure_delay,
                adel=arrival_delay,
                sload=section_load,
                tod=time_of_day,
                cong=congestion,
                created=created.isoformat(),
            ))

        print("\n✅ Seeding complete!")
        print(f"   Stations  : {len(STATIONS)}")
        print(f"   Sections  : {len(SECTIONS)}")
        print(f"   Trains    : {len(TRAINS)}")
        print(f"   Schedules : {sum(len(v) for v in SCHEDULES.values())} stops")
        print(f"   Historical: 250 rows (ML training data)")
        print(f"\nNow call  POST /api/v1/ml/train  to train models on this data.")


if __name__ == "__main__":
    run_seed()
