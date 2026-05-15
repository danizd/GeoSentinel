import asyncio
import json
import logging
import math
import time
from datetime import datetime, timezone
from threading import Lock

import websockets

from services.ais_relay import config
from services.ais_relay.models import AISVessel, Location

logger = logging.getLogger(__name__)


class VesselStore:
    def __init__(self):
        self._vessels: dict[str, AISVessel] = {}
        self._lock = Lock()
        self._connected = False
        self._last_update: datetime | None = None
        self._subscribe_bbox: list[dict] = []

    def update_vessel(self, vessel: AISVessel):
        with self._lock:
            self._vessels[vessel.mmsi] = vessel
            self._last_update = datetime.now(timezone.utc)

    def get_vessels_in_bbox(
        self, ne_lat: float, ne_lon: float, sw_lat: float, sw_lon: float
    ) -> list[AISVessel]:
        with self._lock:
            result = []
            for v in self._vessels.values():
                if v.location is None:
                    continue
                lat = v.location.latitude
                lon = v.location.longitude
                if sw_lat <= lat <= ne_lat and sw_lon <= lon <= ne_lon:
                    result.append(v)
            return result

    def get_all_vessels(self) -> list[AISVessel]:
        with self._lock:
            return list(self._vessels.values())

    @property
    def connected(self) -> bool:
        return self._connected

    @connected.setter
    def connected(self, value: bool):
        self._connected = value

    @property
    def last_update(self) -> datetime | None:
        return self._last_update

    @property
    def vessel_count(self) -> int:
        with self._lock:
            return len(self._vessels)

    def mark_dark_ships(self):
        now = datetime.now(timezone.utc)
        threshold_seconds = config.DARK_SHIP_THRESHOLD_MIN * 60
        with self._lock:
            for v in self._vessels.values():
                try:
                    last = datetime.fromisoformat(
                        v.lastAisUpdate.replace("Z", "+00:00")
                    )
                    age = (now - last).total_seconds()
                    v.isDark = age > threshold_seconds
                except (ValueError, TypeError):
                    pass


def _parse_aisstream_message(msg: dict) -> AISVessel | None:
    meta = msg.get("MetaData", {})
    mmsi = str(meta.get("MMSI", ""))
    if not mmsi:
        return None

    msg_type = msg.get("MessageType", "")
    if msg_type not in ("PositionReport", "PositionReportInterval"):
        return None

    position = msg.get("Message", {}).get("PositionReport", {})
    if not position:
        return None

    lat = position.get("Latitude")
    lon = position.get("Longitude")
    if lat is None or lon is None:
        return None

    sog = position.get("Sog", 0.0)
    cog = position.get("Cog", 0.0)
    heading = position.get("TrueHeading", cog)
    nav_status_code = position.get("NavigationalStatus", 0)
    nav_status_map = {
        0: "under_way_using_engine",
        1: "anchored",
        2: "not_under_command",
        3: "restricted_maneuverability",
        4: "constrained_by_draught",
        5: "moored",
        6: "aground",
        7: "engaged_in_fishing",
        8: "under_way_sailing",
        15: "not_defined",
    }
    nav_status = nav_status_map.get(nav_status_code, "underway")

    rot = position.get("Rot", 0.0)
    sog_val = sog if isinstance(sog, (int, float)) else 0.0
    cog_val = cog if isinstance(cog, (int, float)) else 0.0
    heading_val = heading if isinstance(heading, (int, float)) else cog_val

    name = meta.get("ShipName", "").strip()
    callsign = meta.get("Callsign", "").strip() or None
    ship_type_code = meta.get("ShipType", 0)
    vessel_type = _ship_type_name(ship_type_code)
    flag = _mmsi_to_flag(mmsi)

    timestamp_str = meta.get("time_stamp", "")
    if not timestamp_str:
        timestamp_str = datetime.now(timezone.utc).isoformat()

    return AISVessel(
        id=f"{mmsi}:{int(time.time())}",
        mmsi=mmsi,
        name=name or None,
        callsign=callsign,
        location=Location(latitude=round(float(lat), 4), longitude=round(float(lon), 4)),
        sog=round(float(sog_val), 1),
        cog=round(float(cog_val), 1),
        heading=round(float(heading_val), 1),
        navigationalStatus=nav_status,
        vesselType=vessel_type,
        flag=flag,
        destination=None,
        isDark=False,
        lastAisUpdate=timestamp_str,
        source="aisstream",
    )


def _ship_type_code_to_name(code: int) -> str:
    if 20 <= code <= 29:
        return "wing_in_ground"
    if 30 <= code <= 39:
        return "fishing"
    if 40 <= code <= 49:
        return "tug"
    if 50 <= code <= 59:
        return "pilot"
    if 60 <= code <= 69:
        return "passenger"
    if 70 <= code <= 79:
        return "cargo"
    if 80 <= code <= 89:
        return "tanker"
    if 90 <= code <= 99:
        return "other"
    return "unknown"


_SHIP_TYPE_MAP = {
    30: "fishing",
    31: "towing",
    32: "towing",
    33: "dredging",
    34: "diving_ops",
    35: "military_ops",
    36: "yacht",
    37: "pleasure_craft",
    50: "pilot",
    51: "search_and_rescue",
    52: "tug",
    53: "port_tender",
    54: "pollution_control",
    55: "law_enforcement",
    58: "medical_transport",
    59: "resolution_no18",
    60: "passenger",
    70: "cargo",
    80: "tanker",
    90: "other",
}


def _ship_type_name(code: int) -> str:
    return _SHIP_TYPE_MAP.get(code, _ship_type_code_to_name(code))


_MMSI_PREFIX_TO_FLAG = {
    "201": "AL", "202": "AL", "203": "AL", "204": "AL",
    "205": "AL", "206": "AL", "207": "AL", "208": "AL", "209": "AL",
    "210": "LR", "211": "LR", "212": "LR", "213": "LR",
    "220": "DK", "230": "DK", "240": "DK", "245": "DK",
    "246": "DK", "247": "DK",
    "250": "GB", "251": "GB", "252": "GB", "253": "GB",
    "254": "GB", "255": "GB", "256": "GB", "257": "GB",
    "300": "US", "301": "US", "310": "US", "311": "US", "312": "US",
    "313": "US", "314": "US", "315": "US", "316": "US",
    "338": "US",
    "400": "LY", "401": "LY", "403": "LY", "405": "LY",
    "411": "LY", "412": "LY", "413": "LY",
    "416": "MX", "417": "MX",
    "419": "SA",
    "430": "PH", "431": "PH", "432": "PH", "433": "PH", "434": "PH", "435": "PH",
    "440": "KR", "441": "KR", "442": "KR",
    "450": "CN", "451": "CN", "452": "CN", "453": "CN", "454": "CN",
    "455": "CN", "456": "CN", "457": "CN",
    "500": "MY", "501": "MY", "503": "MY",
    "510": "SG", "511": "SG", "512": "SG", "513": "SG",
    "525": "SG",
    "529": "PG",
    "533": "AU", "538": "AU",
    "600": "ZA", "601": "ZA", "602": "ZA",
    "603": "ZA", "604": "ZA", "605": "ZA", "606": "ZA", "607": "ZA", "608": "ZA",
    "609": "ZA",
    "619": "ZA",
    "620": "EG", "621": "EG", "622": "EG", "623": "EG",
    "636": "GR", "637": "GR",
    "638": "GR", "639": "GR",
    "640": "GR", "641": "GR", "642": "GR", "643": "GR", "644": "GR",
    "645": "GR", "646": "GR", "647": "GR",
    "648": "GR", "649": "GR",
    "670": "GR", "671": "GR", "672": "GR", "673": "GR", "674": "GR",
    "675": "GR", "676": "GR", "677": "GR", "678": "GR", "679": "GR",
    "710": "AE", "711": "AE", "712": "AE",
    "720": "AE", "721": "AE", "722": "AE",
    "730": "SA", "731": "SA",
}


def _mmsi_to_flag(mmsi: str) -> str | None:
    for length in range(3, 0, -1):
        prefix = mmsi[:length]
        if prefix in _MMSI_PREFIX_TO_FLAG:
            return _MMSI_PREFIX_TO_FLAG[prefix]
    return None


store = VesselStore()


async def aisstream_listener(bbox_list: list[dict]):
    if not config.AISSTREAM_API_KEY:
        logger.warning("AISSTREAM_API_KEY not set, using mock data only")
        return

    backoff = config.RECONNECT_BACKOFF_BASE

    while True:
        try:
            subscribe_message = json.dumps(
                {"APIkey": config.AISSTREAM_API_KEY, "BoundingBoxes": bbox_list}
            )

            logger.info(f"Connecting to AISStream WebSocket...")
            async with websockets.connect(
                config.AISSTREAM_WS_URL,
                ping_interval=30,
                ping_timeout=60,
            ) as ws:
                await ws.send(subscribe_message)
                store.connected = True
                logger.info(f"Connected to AISStream, subscribed to {len(bbox_list)} bbox(es)")
                backoff = config.RECONNECT_BACKOFF_BASE

                async for raw_msg in ws:
                    try:
                        data = json.loads(raw_msg)
                        if isinstance(data, list):
                            for item in data:
                                vessel = _parse_aisstream_message(item)
                                if vessel:
                                    store.update_vessel(vessel)
                        elif isinstance(data, dict):
                            vessel = _parse_aisstream_message(data)
                            if vessel:
                                store.update_vessel(vessel)
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        logger.debug(f"Error parsing AISStream message: {e}")

        except (
            websockets.exceptions.ConnectionClosed,
            websockets.exceptions.InvalidStatusCode,
            OSError,
        ) as e:
            store.connected = False
            logger.warning(f"AISStream disconnected: {e}, reconnecting in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, config.RECONNECT_BACKOFF_MAX)

        except Exception as e:
            store.connected = False
            logger.error(f"AISStream error: {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, config.RECONNECT_BACKOFF_MAX)