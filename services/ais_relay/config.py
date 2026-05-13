import os

AIS_SOURCE = os.getenv("AIS_SOURCE", "mock")
AIS_RELAY_PORT = int(os.getenv("AIS_RELAY_PORT", "8003"))
CACHE_TTL_SECONDS = 300
