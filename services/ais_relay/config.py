import os
import json

AISSTREAM_API_KEY = os.getenv("AISSTREAM_API_KEY", "")
AIS_RELAY_PORT = int(os.getenv("AIS_RELAY_PORT", "8003"))
AIS_SOURCE = os.getenv("AIS_SOURCE", "mock")
CACHE_TTL_SECONDS = int(os.getenv("AIS_SNAPSHOT_INTERVAL_MS", "3000")) // 1000
DARK_SHIP_THRESHOLD_MIN = int(os.getenv("DARK_SHIP_THRESHOLD_MIN", "20"))
AISSTREAM_WS_URL = os.getenv("AISSTREAM_WS_URL", "wss://stream.aisstream.io/v0/stream")
RECONNECT_BACKOFF_BASE = int(os.getenv("RECONNECT_BACKOFF_BASE", "2"))
RECONNECT_BACKOFF_MAX = int(os.getenv("RECONNECT_BACKOFF_MAX", "60"))

_AIS_SUBSCRIBE_BBOX_RAW = os.getenv("AIS_SUBSCRIBE_BBOX", "")
AIS_SUBSCRIBE_BBOX: list[dict] = []
if _AIS_SUBSCRIBE_BBOX_RAW:
    try:
        AIS_SUBSCRIBE_BBOX = json.loads(_AIS_SUBSCRIBE_BBOX_RAW)
    except json.JSONDecodeError:
        AIS_SUBSCRIBE_BBOX = []