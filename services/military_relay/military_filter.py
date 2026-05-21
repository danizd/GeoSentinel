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


@lru_cache(maxsize=1)
def _compiled_ranges() -> list[tuple[int, int]]:
    """Convierte MILITARY_HEX_RANGES a pares de enteros para comparacion eficiente.
    Se compila una unica vez gracias a lru_cache.

    Returns:
        Lista de tuplas (hex_min_int, hex_max_int) por rango ICAO militar.
    """
    return [
        (int(lo, 16), int(hi, 16))
        for lo, hi in config.MILITARY_HEX_RANGES
    ]


def is_hex_military_by_range(hex_code: Optional[str]) -> bool:
    """Comprueba si un codigo ICAO24 cae dentro de un rango asignado a uso
    militar por pais segun MILITARY_HEX_RANGES.

    Args:
        hex_code: Codigo ICAO24 en cualquier formato (mayusculas, minusculas,
                  con guiones o espacios).

    Returns:
        True si el codigo pertenece a un rango militar conocido.
    """
    if not hex_code:
        return False
    normalized = hex_code.strip().upper().replace("-", "").replace(" ", "")
    if len(normalized) != 6:
        return False
    try:
        value = int(normalized, 16)
    except ValueError:
        return False
    return any(lo <= value <= hi for lo, hi in _compiled_ranges())


def is_military(hex_code: Optional[str], callsign: Optional[str], category: int | None = None) -> bool:
    """Determina si una aeronave es militar por cualquiera de los criterios
    disponibles, en orden de fiabilidad decreciente.

    Prioridad: category==7 -> rango ICAO -> hex individual -> callsign+hex.
    El callsign solo no es suficiente: requiere confirmacion de hex para evitar
    falsos positivos con prefijos de 3 letras que coincidan con aerolineas civiles.

    Args:
        hex_code: Codigo ICAO24 de la aeronave.
        callsign: Indicativo de vuelo.
        category: Categoria ADS-B (7 = militar segun estandar ICAO).

    Returns:
        True si la aeronave es militar por alguno de los criterios.
    """
    if category == 7:
        return True
    hex_confirmed = is_hex_military_by_range(hex_code) or is_hex_military(hex_code)
    if hex_confirmed:
        return True
    # Callsign actua como refuerzo solo si el hex ya confirma la aeronave
    if is_callsign_military(callsign) and hex_confirmed:
        return True
    return False


def normalize_hex(hex_code: Optional[str]) -> Optional[str]:
    if not hex_code:
        return None
    return hex_code.strip().upper().replace("-", "").replace(" ", "")
