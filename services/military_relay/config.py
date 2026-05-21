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
    # --- Ampliación con lista verificada (fuente: comunidad FR24) ---
    "RRR", "RFF", "RSD",                          # RAF / Rusia Fed. / Rossiya Special
    "GAM",                                         # Luftwaffe (alternativo)
    "FMY", "FNY", "FNF",                           # Ejército/Marina/Fuerza Aérea Francia
    "IAM",                                         # Aeronautica Militare Italiana
    "DNY", "NVY",                                  # Marina Danesa / Navy genérico
    "MMF",                                         # NATO Multinational MRTT Fleet
    "UAF", "AIO",                                  # Ucrania / Air India Ops (military charter)
    "UNO",                                         # Naciones Unidas (peacekeeping)
    "DOD",                                         # US Department of Defense
    "AFB", "AAC", "CEF", "CXG",                    # Bases/unidades USAF y afines
    "CHD", "SHF", "SUI", "SIV", "SQF",            # Escuadrones varios
    "AFP", "PNY", "NOW", "KIW",                    # Unidades adicionales
    "LAF", "IFC", "HUF",                           # Letonia, Iran, Hungría AF
    "ASY", "HVK", "HRZ", "EEF",                    # Unidades nórdicas/bálticas
    "AYB", "NOH", "WAD", "RSF", "QID",            # Otras unidades verificadas
]

CALLSIGN_PREFIXES_SHORT = [
    "AE", "RF", "TF", "PAT", "SAM",
    "OPS", "CTF", "IRG", "TAF",
]

MILITARY_HEX_RANGES: list[tuple[str, str]] = [
    ("AE0000", "AFFFFF"),  # USA (USAF / USN / USMC / USCG)
    ("C00000", "C07FFF"),  # Canada (RCAF)
    ("3A0000", "3AFFFF"),  # Francia (Armée de l'Air et de l'Espace)
    ("43C000", "43CFFF"),  # Reino Unido (RAF / Royal Navy)
    ("01C000", "01FFFF"),  # Rusia (VKS)
    ("E4E000", "E4EFFF"),  # Israel (IAF)
    ("3C4000", "3C7FFF"),  # Alemania (Luftwaffe)
    ("340000", "347FFF"),  # España (Ejército del Aire)
    ("300000", "303FFF"),  # Italia (Aeronautica Militare)
    ("44C000", "44CFFF"),  # Bélgica (BAF) / NATO AWACS
    ("480000", "480FFF"),  # Países Bajos (RNLAF)
    ("710000", "717FFF"),  # Suecia (Flygvapnet)
    ("47A000", "47AFFF"),  # Noruega (RNoAF)
    ("489000", "48AFFF"),  # Polonia (Siły Lotnicze)
    ("4B8000", "4BFFFF"),  # Turquía (THK)
    ("7C0000", "7C3FFF"),  # Australia (RAAF)
    ("7B0000", "7BFFFF"),  # China (PLAAF / PLAN)
    ("E40000", "E40FFF"),  # Brasil (FAB)
    ("71C000", "71FFFF"),  # Corea del Sur (ROKAF)
    ("738000", "73FFFF"),  # Japón (JASDF / JMSDF)
]