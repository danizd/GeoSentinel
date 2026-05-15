import asyncio
import logging
import random
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from services.ais_relay import config
from services.ais_relay.models import AISVessel, AISVesselsResponse, Location
from services.ais_relay.aisstream_client import store, aisstream_listener

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AIS Vessel Relay",
    description="AIS vessel tracking relay",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MOCK_SHIPS = [
    ("USS Arleigh Burke", "DDG-51", "military_ops", "US"),
    ("USS Nimitz", "CVN-68", "military_ops", "US"),
    ("HMS Queen Elizabeth", "R08", "military_ops", "GB"),
    ("FS Charles de Gaulle", "R91", "military_ops", "FR"),
    ("RFS Admiral Kuznetsov", "063", "military_ops", "RU"),
    ("PLAN Liaoning", "16", "military_ops", "CN"),
    ("IRIS Makran", "441", "military_ops", "IR"),
    ("TCG Anadolu", "L-400", "military_ops", "TR"),
    ("HMAS Canberra", "L02", "military_ops", "AU"),
    ("ITS Cavour", "550", "military_ops", "IT"),
]

MOCK_POSITIONS = [
    (35.5, 15.5, 12, 90),
    (33.5, 31.0, 8, 270),
    (50.0, -1.0, 15, 45),
    (41.5, 5.0, 10, 180),
    (43.0, 34.5, 5, 315),
    (16.5, 111.5, 12, 60),
    (25.5, 57.5, 6, 140),
    (39.0, 25.5, 14, 225),
    (-35.5, 115.5, 16, 350),
    (38.5, 13.5, 9, 160),
]


def _generate_mock_vessels(
    bbox: tuple[float, float, float, float],
) -> list[AISVessel]:
    ne_lat, ne_lon, sw_lat, sw_lon = bbox
    vessels: list[AISVessel] = []
    now = datetime.now(timezone.utc)

    for i, (name, hull, vtype, flag) in enumerate(MOCK_SHIPS):
        lat, lon, sog, cog = MOCK_POSITIONS[i]
        lat += random.uniform(-0.3, 0.3)
        lon += random.uniform(-0.3, 0.3)

        if not (sw_lat <= lat <= ne_lat and sw_lon <= lon <= ne_lon):
            continue

        mmsi = f"{100000000 + i:09d}"
        ts = int(now.timestamp())
        vessel = AISVessel(
            id=f"{mmsi}:{ts}",
            mmsi=mmsi,
            name=name,
            callsign=hull,
            location=Location(latitude=round(lat, 4), longitude=round(lon, 4)),
            sog=round(sog + random.uniform(-2, 2), 1),
            cog=round(cog + random.uniform(-5, 5), 1),
            heading=round(cog + random.uniform(-5, 5), 1),
            navigationalStatus="under_way_using_engine",
            vesselType=vtype,
            flag=flag,
            destination="patrol",
            isDark=False,
            lastAisUpdate=now.isoformat(),
            source="mock",
        )
        vessels.append(vessel)

    return vessels


@app.get("/api/ais/v1/list-vessels")
async def list_vessels(
    neLat: float = Query(..., description="North east latitude"),
    neLon: float = Query(..., description="North east longitude"),
    swLat: float = Query(..., description="South west latitude"),
    swLon: float = Query(..., description="South west longitude"),
) -> AISVesselsResponse:
    if neLat <= swLat or neLon <= swLon:
        raise HTTPException(status_code=400, detail="Invalid bbox")
    if neLat > 90 or neLat < -90 or swLat > 90 or swLat < -90:
        raise HTTPException(status_code=400, detail="Latitude out of range")
    if neLon > 180 or neLon < -180 or swLon > 180 or swLon < -180:
        raise HTTPException(status_code=400, detail="Longitude out of range")

    bbox = (neLat, neLon, swLat, swLon)

    real_vessels = store.get_vessels_in_bbox(neLat, neLon, swLat, swLon)

    if real_vessels:
        logger.info(f"Returning {len(real_vessels)} real vessels for bbox")
        is_stale = not store.connected
        return AISVesselsResponse(
            vessels=real_vessels,
            clusters=[],
            isStale=is_stale,
            timestamp=datetime.now(timezone.utc),
        )

    mock_vessels = _generate_mock_vessels(bbox)
    logger.info(f"Returning {len(mock_vessels)} mock vessels for bbox")
    return AISVesselsResponse(
        vessels=mock_vessels,
        clusters=[],
        isStale=True,
        timestamp=datetime.now(timezone.utc),
    )


@app.get("/health/ais")
async def health():
    return {
        "upstream_connected": store.connected,
        "vessel_count": store.vessel_count,
        "last_update": store.last_update.isoformat() if store.last_update else None,
        "source": "aisstream" if store.connected else ("stale" if store.vessel_count > 0 else "mock"),
    }


WORLD_BBOX = [{"minLatitude": -90, "maxLatitude": 90, "minLongitude": -180, "maxLongitude": 180}]


@app.on_event("startup")
async def startup():
    if config.AISSTREAM_API_KEY:
        bbox_list = config.AIS_SUBSCRIBE_BBOX if config.AIS_SUBSCRIBE_BBOX else WORLD_BBOX
        asyncio.create_task(aisstream_listener(bbox_list))
        logger.info("AISStream listener started")
    else:
        logger.warning("AISSTREAM_API_KEY not set, using mock data only")