from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.database import get_db
from models.sources_metadata import SourcesMetadata
from models.incidents import Incident
from models.events_canonical import EventsCanonical

router = APIRouter()


@router.get("/seed")
def seed_test_data(db: Session = Depends(get_db)):
    existing = db.query(SourcesMetadata).first()
    if not existing:
        sources = [
            SourcesMetadata(source="gdelt", display_name="GDELT", independence_class="media_derived"),
            SourcesMetadata(source="usgs", display_name="USGS Earthquake", independence_class="sensor"),
            SourcesMetadata(source="firms", display_name="FIRMS NASA", independence_class="sensor"),
            SourcesMetadata(source="acled", display_name="ACLED", independence_class="field_reported"),
        ]
        db.add_all(sources)
        db.commit()

    incidents_data = [
        {"event_type": "conflict_battle", "category": "conflict", "lat": 40.0, "lon": -3.0, "severity": 7.5, "confidence": 8.0},
        {"event_type": "earthquake", "category": "disaster_natural", "lat": 35.0, "lon": -120.0, "severity": 6.0, "confidence": 9.0},
        {"event_type": "wildfire_hotspot", "category": "wildfire", "lat": 45.0, "lon": -110.0, "severity": 5.0, "confidence": 7.0},
    ]

    count = 0
    for i, data in enumerate(incidents_data):
        inc = Incident(
            incident_id=uuid4(),
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            event_type=data["event_type"],
            category=data["category"],
            status="open",
            canonical_point=f"POINT({data['lon']} {data['lat']})",
            severity_max=data["severity"],
            severity_latest=data["severity"],
            confidence=data["confidence"],
            source_count=1,
            observation_count=1,
            sources=["gdelt"],
        )
        db.add(inc)
        count += 1

    db.commit()

    return {"message": f"Seeded {count} test incidents"}