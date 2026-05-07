import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from models.events_canonical import EventsCanonical
from models.incidents import Incident

logger = logging.getLogger(__name__)

KM_MAX = {
    "conflict": 50.0,
    "wildfire": 20.0,
    "earthquake": 100.0,
    "disaster_natural": 75.0,
    "mobility": 30.0,
}

HOURS_MAX = {
    "conflict": 48.0,
    "wildfire": 24.0,
    "earthquake": 2.0,
    "disaster_natural": 72.0,
    "mobility": 6.0,
}

WEIGHTS_SPACE = {
    "conflict": 0.6,
    "wildfire": 0.7,
    "earthquake": 0.5,
    "disaster_natural": 0.5,
    "mobility": 0.8,
}

WEIGHTS_TIME = {
    "conflict": 0.4,
    "wildfire": 0.3,
    "earthquake": 0.5,
    "disaster_natural": 0.5,
    "mobility": 0.2,
}

EPSILON = {
    "conflict": 0.15,
    "wildfire": 0.20,
    "earthquake": 0.10,
    "disaster_natural": 0.15,
    "mobility": 0.12,
}

INDEPENDENCE_FACTORS = {
    "sensor": 2.0,
    "field_reported": 1.5,
    "media_derived": 0.5,
}

SOURCE_INDEPENDENCE_CLASS = {
    "usgs": "sensor",
    "firms": "sensor",
    "acled": "field_reported",
    "gdelt": "media_derived",
    "adsb": "sensor",
    "marinetraffic": "sensor",
    "liveuamap": "media_derived",
}

MIN_SAMPLES_BY_CLASS = {
    "sensor": 1,
    "field_reported": 1,
    "media_derived": 2,
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    R = 6371.0
    lat1_r, lon1_r = radians(lat1), radians(lon1)
    lat2_r, lon2_r = radians(lat2), radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    return R * c


def compute_mixed_distance(
    lat1: float, lon1: float, time1: datetime,
    lat2: float, lon2: float, time2: datetime,
    category: str,
) -> float:
    km_max = KM_MAX.get(category, 50.0)
    hours_max = HOURS_MAX.get(category, 48.0)
    w_space = WEIGHTS_SPACE.get(category, 0.5)
    w_time = WEIGHTS_TIME.get(category, 0.5)

    dist_km = haversine_km(lat1, lon1, lat2, lon2)
    time_diff_hours = abs((time1 - time2).total_seconds()) / 3600

    normalized_dist = dist_km / km_max if km_max > 0 else 0
    normalized_time = time_diff_hours / hours_max if hours_max > 0 else 0

    return w_space * normalized_dist + w_time * normalized_time


def compute_confidence(events: list[EventsCanonical]) -> float:
    if not events:
        return 0.0

    score = 0.0
    seen_media_cycle = set()

    for event in events:
        source_class = SOURCE_INDEPENDENCE_CLASS.get(event.source, "media_derived")
        factor = INDEPENDENCE_FACTORS.get(source_class, 0.5)

        if source_class == "media_derived":
            cycle_hour = event.event_time.replace(minute=0, second=0, microsecond=0)
            cycle_key = f"{event.source}:{cycle_hour.isoformat()}"
            if cycle_key in seen_media_cycle:
                factor *= 0.1
            seen_media_cycle.add(cycle_key)

        score += factor

    max_expected = 8.0
    return min(score * 10 / max_expected, 10.0)


def _parse_geometry_coords(point) -> tuple[float, float]:
    if hasattr(point, "coords"):
        return point.coords[1], point.coords[0]
    if hasattr(point, "wkt"):
        wkt = point.wkt
        if wkt.startswith("POINT("):
            coords = wkt.replace("POINT(", "").replace(")", "").split()
            return float(coords[1]), float(coords[0])
    if isinstance(point, str) and point.startswith("POINT("):
        coords = point.replace("POINT(", "").replace(")", "").split()
        return float(coords[1]), float(coords[0])
    return 0.0, 0.0


def compute_canonical_point(events: list[EventsCanonical]) -> tuple[float, float]:
    total_weight = sum(e.confidence for e in events)
    if total_weight == 0:
        lat, lon = _parse_geometry_coords(events[0].location_point)
        return lat, lon

    lat = sum(_parse_geometry_coords(e.location_point)[0] * e.confidence for e in events) / total_weight
    lon = sum(_parse_geometry_coords(e.location_point)[1] * e.confidence for e in events) / total_weight

    return lat, lon


def get_linked_event_ids(events: list[EventsCanonical]) -> list[int]:
    return [e.id for e in events]


def get_linked_sources(events: list[EventsCanonical]) -> list[str]:
    return list(set(e.source for e in events))


def find_closest_incident(
    event: EventsCanonical,
    incidents: list[Incident],
    category: str,
) -> Incident | None:
    if not incidents:
        return None

    eps = EPSILON.get(category, 0.15)

    event_lat, event_lon = _parse_geometry_coords(event.location_point)
    event_time = event.event_time

    best_incident = None
    best_distance = float("inf")

    for inc in incidents:
        if inc.canonical_point is None:
            continue

        inc_lat, inc_lon = _parse_geometry_coords(inc.canonical_point)
        inc_time = inc.last_seen

        distance = compute_mixed_distance(
            event_lat, event_lon, event_time,
            inc_lat, inc_lon, inc_time,
            category,
        )

        if distance < eps and distance < best_distance:
            best_distance = distance
            best_incident = inc

    return best_incident


def assign_event_to_incident(session: Session, event: EventsCanonical, incident: Incident) -> None:
    from jobs.incident_lifecycle import transition_to_updated

    event_linked_ids = incident.linked_event_ids or []
    if event.id not in event_linked_ids:
        event_linked_ids.append(event.id)

    incident.linked_event_ids = event_linked_ids

    new_sources = set(incident.sources or [])
    new_sources.add(event.source)
    incident.sources = list(new_sources)

    incident.observation_count = len(event_linked_ids)
    incident.source_count = len(new_sources)

    incident.last_seen = max(incident.last_seen, event.event_time) if incident.last_seen else event.event_time
    incident.last_updated = datetime.now(timezone.utc)
    incident.severity_latest = event.severity

    transition_to_updated(session, incident)


def create_new_incident(session: Session, event: EventsCanonical) -> Incident:
    from jobs.incident_lifecycle import transition_to_open

    now = datetime.now(timezone.utc)

    incident = Incident(
        first_seen=event.event_time,
        last_seen=event.event_time,
        last_updated=now,
        event_type=event.event_type,
        category=event.category,
        country_iso2=event.country_iso2,
        admin1=event.admin1,
        status="open",
        status_changed_at=now,
        canonical_point=f"POINT({event.location_point.coords[0]} {event.location_point.coords[1]})",
        canonical_geometry=None,
        severity_max=event.severity,
        severity_latest=event.severity,
        confidence=event.confidence,
        fatalities_total=event.fatalities or 0,
        source_count=1,
        observation_count=1,
        sources=[event.source],
        linked_event_ids=[event.id],
    )

    session.add(incident)
    session.commit()
    session.refresh(incident)

    event_linked_ids = event.raw_event_id
    logger.info(f"Created new incident {incident.incident_id} for event {event.id}")

    return incident


def fetch_unassigned_events(session: Session, since: datetime) -> list[EventsCanonical]:
    return session.execute(
        select(EventsCanonical)
        .where(EventsCanonical.event_time >= since)
        .order_by(EventsCanonical.event_time)
    ).scalars().all()


def fetch_active_incidents(session: Session, category: str) -> list[Incident]:
    return session.execute(
        select(Incident)
        .where(
            Incident.category == category,
            Incident.status.in_(["open", "updated"]),
        )
    ).scalars().all()


def run_clustering_job(session: Session, last_run_time: datetime | None = None) -> dict[str, Any]:
    if last_run_time is None:
        last_run_time = datetime.now(timezone.utc) - timedelta(hours=24)

    new_events = fetch_unassigned_events(session, last_run_time)

    if not new_events:
        logger.info("No new events to cluster")
        return {"created": 0, "assigned": 0, "total_events": 0}

    categories = list(set(e.category for e in new_events))

    created = 0
    assigned = 0

    for category in categories:
        cat_events = [e for e in new_events if e.category == category]
        if not cat_events:
            continue

        active_incidents = fetch_active_incidents(session, category)

        for event in cat_events:
            best_incident = find_closest_incident(event, active_incidents, category)

            if best_incident:
                assign_event_to_incident(session, event, best_incident)
                assigned += 1
            else:
                create_new_incident(session, event)
                created += 1
                active_incidents = fetch_active_incidents(session, category)

    return {
        "created": created,
        "assigned": assigned,
        "total_events": len(new_events),
    }


if __name__ == "__main__":
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    logging.basicConfig(level=logging.INFO)

    engine = create_engine(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel"))
    Session = sessionmaker(bind=engine)

    session = Session()
    try:
        result = run_clustering_job(session)
        logger.info(f"Clustering job result: {result}")
    finally:
        session.close()