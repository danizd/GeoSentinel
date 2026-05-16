import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True), override=False)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel")

if not db_url:
    print("ERROR: DATABASE_URL no esta definida.")
    sys.exit(1)

engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

access_token = os.getenv("ACLED_ACCESS_TOKEN") or None
username = os.getenv("ACLED_USERNAME") or None
password = os.getenv("ACLED_PASSWORD") or None

if not access_token and (not username or not password):
    print("ERROR: ACLED_ACCESS_TOKEN o ACLED_USERNAME/ACLED_PASSWORD no estan definidas.")
    print("  Obtener en: https://acleddata.com/myacled")
    sys.exit(1)

from backend.ingestors.acled_ingestor import ACLEDIngestor

def main():
    ingestor = ACLEDIngestor(
        access_token=access_token,
        username=username,
        password=password,
    )
    session = Session()

    try:
        print("=" * 60)
        print("ACLED — Conflictos (ultimas 48h + backfill)")
        print("=" * 60)

        result = ingestor.run(session)

        print("\n  processed:     {0}".format(result.get('processed', 0)))
        print("  quarantined:   {0}".format(result.get('quarantined', 0)))
        print("  duplicates:    {0}".format(result.get('duplicates', 0)))
        print("  total_fetched: {0}".format(result.get('total_fetched', 0)))

    except Exception as e:
        print("ERROR: {0}".format(e))
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()