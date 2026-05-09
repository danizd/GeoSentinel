import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from jobs.clustering_job import run_clustering_job

db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel")

engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

with Session() as session:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    result = run_clustering_job(session, last_run_time=since)
    print(f"  -> Incidentes creados    : {result.get('created', 0)}")
    print(f"  -> Eventos asignados     : {result.get('assigned', 0)}")
    print(f"  -> Total eventos         : {result.get('total_events', 0)}")
