import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel")

if not db_url:
    print("ERROR: DATABASE_URL no esta definida.")
    sys.exit(1)

engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

api_key = os.getenv("GDELT_API_KEY")
if not api_key:
    print("ERROR: GDELT_API_KEY no esta definida.")
    print("  Registrate en: https://gdeltcloud.com/register")
    sys.exit(1)

from ingestors.gdelt_ingestor import GDELTCloudIngestor

def main():
    ingestor = GDELTCloudIngestor(api_key=api_key)
    session = Session()

    try:
        print("=" * 60)
        print("GDELT Cloud — Zonas de conflicto")
        print("=" * 60)

        result = ingestor.run_all_zones(session, lookback_days=1)

        print("\n  processed:     {0}".format(result.get('processed', 0)))
        print("  quarantined:   {0}".format(result.get('quarantined', 0)))
        print("  duplicates:    {0}".format(result.get('duplicates', 0)))
        print("  total_fetched: {0}".format(result.get('total_fetched', 0)))

    except Exception as e:
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
