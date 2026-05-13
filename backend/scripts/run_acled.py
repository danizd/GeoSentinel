import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel")

if not db_url:
    print("ERROR: DATABASE_URL no esta definida.")
    sys.exit(1)

engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

api_key = os.getenv("ACLED_API_KEY")
api_email = os.getenv("ACLED_EMAIL")

if not api_key or not api_email:
    print("ERROR: ACLED_API_KEY o ACLED_EMAIL no estan definidas.")
    print("  Obtener en: https://acleddata.com/myacled")
    sys.exit(1)

from backend.ingestors.acled_ingestor import ACLEDIngestor

def main():
    ingestor = ACLEDIngestor(api_key=api_key, api_email=api_email)
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
