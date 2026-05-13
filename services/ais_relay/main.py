import logging
import random
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from services.ais_relay import config
from services.ais_relay.models import (
    AISVessel,
    AISVesselsResponse,
    Location,
)

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

SHIP_NAMES = [
    ("USS Arleigh Burke", "DDG-51", "warship", "US"),
    ("USS Nimitz", "CVN-68", "warship", "US"),
    ("HMS Queen Elizabeth", "R08", "warship", "GB"),
    ("FS Charles de Gaulle", "R91", "warship", "FR"),
    ("RFS Admiral Kuznetsov", "063", "warship", "RU"),
    ("PLAN Liaoning", "16", "warship", "CN"),
    ("IRIS Makran", "441", "warship", "IR"),
    ("TCG Anadolu", "L-400", "warship", "TR"),
    ("HMAS Canberra", "L02", "warship", "AU"),
    ("ITS Cavour", "550", "warship", "IT"),
]

SHIP_POSITIONS = [
    (36.5, 14.3, 12, 90),   # Mediterranean
    (34.0, 33.0, 8, 270),   # Eastern Med
    (51.5, 2.0, 15, 45),    # English Channel
    (43.0, 6.0, 10, 180),   # Western Med
    (44.5, 37.0, 5, 315),   # Black Sea
    (18.0, 113.0, 12, 60),  # South China Sea
    (27.0, 56.0, 6, 140),   # Strait of Hormuz
    (40.5, 27.0, 14, 225),  # Aegean Sea
    (-35.0, 115.0, 16, 350),# SW Australia
    (38.0, 14.0, 9, 160),   # Tyrrhenian Sea
]


def _generate_vessels(bbox: tuple[float, float, float, float]) -> list[AISVessel]:
    neLat, neLon, swLat, swLon = bbox
    vessels: list[AISVessel] = []
    now = datetime.now(timezone.utc)

    for i, (name, hull, vtype, flag) in enumerate(SHIP_NAMES):
        lat, lon, sog, cog = SHIP_POSITIONS[i]
        lat += random.uniform(-0.5, 0.5)
        lon += random.uniform(-0.5, 0.5)

        if not (swLat <= lat <= neLat and swLon <= lon <= neLon):
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
            navigationalStatus="underway",
            vesselType=vtype,
            flag=flag,
            destination="patrol" if vtype == "warship" else "unknown",
            isDark=random.random() < 0.1,
            lastAisUpdate=now.isoformat(),
            source="aisstream",
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

    vessels = _generate_vessels((neLat, neLon, swLat, swLon))
    logger.info(f"Returning {len(vessels)} vessels for bbox")

    return AISVesselsResponse(
        vessels=vessels,
        clusters=[],
        isStale=False,
        timestamp=datetime.now(timezone.utc),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=config.AIS_RELAY_PORT)
