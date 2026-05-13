import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_TTL_SECONDS = 300
MILITARY_HEX_FILE = DATA_DIR / "military_hex.txt"

MILITARY_SOURCE = os.getenv("MILITARY_SOURCE", "opensky")

OPENSKY_CLIENT_ID = os.getenv("OPENSKY_CLIENT_ID", "")
OPENSKY_CLIENT_SECRET = os.getenv("OPENSKY_CLIENT_SECRET", "")
OPENSKY_BASE_URL = "https://opensky-network.org/api"
OPENSKY_TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"

ADSB_API_KEY = os.getenv("ADSB_API_KEY", "")
ADSB_AUTH_HEADER = os.getenv("ADSB_AUTH_HEADER", "api-auth")
ADSB_BASE_URL = os.getenv("ADSB_BASE_URL", "https://adsbexchange.com/api/aircraft")

CALLSIGN_PREFIXES_FULL = [
    "RCH", "REACH", "MOOSE", "EVAC", "DUSTOFF",
    "VIPER", "RAPTOR", "SENTRY", "AWACS", "COBRA", "PYTHON",
    "NAVY", "USAF", "USN", "USMC", "NATO", "RAF",
    "IAF", "VKS", "PLAAF", "FAF", "GAF", "AME",
    "ITAF", "PLF", "TUAF", "RFR", "SVF", "NAF",
    "BAF", "HAF", "ROF", "HUAF", "CFC", "RCAF",
    "ASF", "DAF", "BLUE", "RED", "GOLD",
    "LION", "MACE", "SABER", "STORM", "THNDR",
    "DEMON", "HAWK", "EAGLE", "FALCON", "HORNET",
    "RAVEN", "DRAGON", "PHANTOM", "TIGER", "WOLF",
    "SPAR", "HKY", "CNV", "VV",
]

CALLSIGN_PREFIXES_SHORT = [
    "AE", "RF", "TF", "PAT", "SAM",
    "OPS", "CTF", "IRG", "TAF",
]