import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ingestors.usgs_ingestor import USGSIngestor

db_url = (os.environ.get("DATABASE_URL") or "").strip()
if not db_url:
    print("ERROR: DATABASE_URL no esta definida.")
    sys.exit(1)

engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

with Session() as session:
    result = USGSIngestor().run(session, lookback_hours=24)
    print(f"  -> Procesados : {result['processed']}")
    print(f"  -> Duplicados : {result['duplicates']}")
    print(f"  -> Cuarentena : {result['quarantined']}")
    print(f"  -> Total      : {result['total_fetched']}")
