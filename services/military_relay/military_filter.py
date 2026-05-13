import re
from functools import lru_cache
from typing import Optional

from services.military_relay import config


@lru_cache(maxsize=1)
def load_military_hex_set() -> set[str]:
    hex_set: set[str] = set()
    hex_file = config.MILITARY_HEX_FILE
    if hex_file.exists():
        with open(hex_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip().upper()
                if line and len(line) == 6:
                    hex_set.add(line)
    return hex_set


def reload_military_hex_cache() -> None:
    load_military_hex_set.cache_clear()


def is_callsign_military(callsign: str) -> bool:
    if not callsign:
        return False
    cs = callsign.strip().upper()

    for prefix in config.CALLSIGN_PREFIXES_FULL:
        if cs.startswith(prefix):
            return True

    short_pattern = "|".join(config.CALLSIGN_PREFIXES_SHORT)
    pattern = rf"^({short_pattern})\d+"
    if re.match(pattern, cs):
        return True

    return False


def is_hex_military(hex_code: Optional[str]) -> bool:
    if not hex_code:
        return False
    normalized = hex_code.strip().upper().replace("-", "").replace(" ", "")
    return normalized in load_military_hex_set()


def is_military(hex_code: Optional[str], callsign: Optional[str], category: int | None = None) -> bool:
    if category == 7:
        return True

    if is_callsign_military(callsign) and is_hex_military(hex_code):
        return True

    if is_hex_military(hex_code):
        return True

    if is_callsign_military(callsign):
        return True

    return False


def normalize_hex(hex_code: Optional[str]) -> Optional[str]:
    if not hex_code:
        return None
    return hex_code.strip().upper().replace("-", "").replace(" ", "")