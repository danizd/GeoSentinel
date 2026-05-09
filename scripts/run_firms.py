import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel")

if not db_url:
    print("ERROR: DATABASE_URL no esta definida.")
    sys.exit(1)

engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

map_key = os.getenv("FIRMS_MAP_KEY")
if not map_key:
    print("ERROR: FIRMS_MAP_KEY no esta definida.")
    sys.exit(1)

from ingestors.firms_ingestor import FIRMSIngestor, get_active_aois

def main():
    ingestor = FIRMSIngestor(map_key=map_key)
    session = Session()

    try:
        bboxes = get_active_aois(session)
        if not bboxes:
            print("No AOIs activos. Usando bbox global: -180,-90,180,90")
            bboxes = [(-180, -90, 180, 90)]
        else:
            print(f"Usando {len(bboxes)} AOI(s) activo(s)")

        total_processed = 0
        total_quarantined = 0
        total_duplicates = 0

        for bbox in bboxes:
            result = ingestor.run(session, bbox=bbox)
            print(f"Bbox {bbox}:")
            print(f"  processed:           {result.get('processed', 0)}")
            print(f"  quarantined:          {result.get('quarantined', 0)}")
            print(f"  duplicates:           {result.get('duplicates', 0)}")
            print(f"  skipped_low_confidence: {result.get('skipped_low_confidence', 0)}")
            print(f"  skipped_invalid_type:    {result.get('skipped_invalid_type', 0)}")
            print(f"  total_fetched:       {result.get('total_fetched', 0)}")
            total_processed += result.get('processed', 0)
            total_quarantined += result.get('quarantined', 0)
            total_duplicates += result.get('duplicates', 0)

        print(f"\nTotales:")
        print(f"  processed:    {total_processed}")
        print(f"  quarantined:  {total_quarantined}")
        print(f"  duplicates:   {total_duplicates}")

    except Exception as e:
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
