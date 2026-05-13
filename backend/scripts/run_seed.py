import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models.sources_metadata import SourcesMetadata

db_url = (os.environ.get("DATABASE_URL") or "").strip()
if not db_url:
    print("ERROR: DATABASE_URL no esta definida.")
    sys.exit(1)

engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

SOURCES = [
    ("gdelt", "GDELT Cloud Events v2", "media_derived"),
    ("usgs", "USGS Earthquake Hazards", "sensor"),
    ("firms", "FIRMS NASA (VIIRS/MODIS)", "sensor"),
    ("acled", "ACLED (CC BY-NC 4.0)", "field_reported"),
]

with Session() as session:
    existing = {s.source for s in session.query(SourcesMetadata).all()}
    inserted = 0
    for source, display_name, ind_class in SOURCES:
        if source in existing:
            continue
        session.add(SourcesMetadata(
            source=source,
            display_name=display_name,
            independence_class=ind_class,
        ))
        inserted += 1
    session.commit()
    print(f"  -> Sources insertadas: {inserted}  (ya existian: {len(existing)})")
