"""Actualiza data/military_hex.txt descargando la base de datos de aeronaves de
OpenSky Network y extrayendo todos los ICAO24 clasificados como militares.

Criterios de clasificación:
  1. categoryDescription contiene 'military' (fuente: transponder ADS-B / BD OpenSky)
  2. operator o owner contiene palabras clave de fuerzas armadas conocidas

Esto replica el filtro 'U' del mapa de OpenSky (map.opensky-network.org).
Se ejecuta en background al arrancar el relay; no bloquea el servidor.

Ejecución manual:
    python -m services.military_relay.update_military_db
"""

import csv
import io
import logging
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from services.military_relay import config

logger = logging.getLogger(__name__)

OPENSKY_DB_BASE_URL = "https://s3.opensky-network.org/data-samples/metadata"

# Palabras clave en categoryDescription que indican aeronave militar
MILITARY_CATEGORY_KEYWORDS: frozenset[str] = frozenset({"military"})

# Palabras clave en operator / owner que indican organización militar.
# Se usan substrings para cubrir variaciones idiomáticas.
MILITARY_OPERATOR_KEYWORDS: frozenset[str] = frozenset({
    "air force", "airforce", "navy", "army", "marines", "luftwaffe",
    "military", "militaire", "fuerza aérea", "fuerza aerea",
    "royal air force", "usaf", "usmc", "defence", "defense",
    "bundeswehr", "armée", "armada", "ejército del aire", "ejercito del aire",
    "aeronautica militare", "siły lotnicze", "force aérienne",
    "marine nationale", "marina militar", "royal navy",
    "coast guard", "guardia costera", "garde côtière",
    "forces armées", "fuerzas armadas", "aeronautique militaire",
    "aviation militaire", "heeresflieger", "marineflieger",
    "exercito", "ejercito", "fuerza aerea",
})


def _is_military_row(row: dict) -> bool:
    """Determina si una fila del CSV de OpenSky corresponde a una aeronave militar.

    Args:
        row: Fila del CSV como dict (campos del aircraft database de OpenSky).

    Returns:
        True si la aeronave es militar según categoría u operador/propietario.
    """
    category = row.get("categoryDescription", "").strip().lower()
    if any(kw in category for kw in MILITARY_CATEGORY_KEYWORDS):
        return True

    operator = row.get("operator", "").strip().lower()
    owner = row.get("owner", "").strip().lower()
    combined = f"{operator} {owner}"
    return any(kw in combined for kw in MILITARY_OPERATOR_KEYWORDS)


def _try_download(date_str: str, timeout: int = 120) -> Optional[str]:
    """Descarga el CSV de OpenSky para el mes indicado (YYYY-MM).

    Args:
        date_str: Mes en formato 'YYYY-MM'.
        timeout: Segundos antes de abortar la conexión.

    Returns:
        Contenido del CSV como str, o None si la descarga falla.
    """
    url = f"{OPENSKY_DB_BASE_URL}/aircraft-database-complete-{date_str}.csv"
    try:
        logger.info(f"Descargando BD OpenSky: {url}")
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read()
            content = raw.decode("utf-8", errors="replace")
            logger.info(f"Descarga OK ({date_str}): {len(raw):,} bytes")
            return content
    except Exception as exc:
        logger.warning(f"Descarga fallida para {date_str}: {exc}")
        return None


def download_and_extract_military_hex(output_file: Path) -> int:
    """Descarga la BD de aeronaves de OpenSky y extrae los ICAO24 militares.

    Intenta el mes actual y los dos anteriores como fallback. Escribe los
    resultados en output_file solo si se encontraron aeronaves; de lo contrario
    conserva el archivo existente sin modificarlo.

    Args:
        output_file: Ruta del fichero de salida (military_hex.txt).

    Returns:
        Número de ICAO24 militares encontrados; 0 si la descarga o el proceso falló.
    """
    now = datetime.now(timezone.utc)
    candidates: list[str] = []
    for offset in range(3):
        month = now.month - offset
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        candidates.append(f"{year}-{month:02d}")

    content: Optional[str] = None
    for date_str in candidates:
        content = _try_download(date_str)
        if content:
            break

    if not content:
        logger.error(
            "No se pudo descargar la BD de OpenSky en ningún intento. "
            "Se conserva el military_hex.txt existente."
        )
        return 0

    military_hex: set[str] = set()
    try:
        reader = csv.DictReader(io.StringIO(content), quotechar="'")
        processed = 0
        for row in reader:
            processed += 1
            if processed % 100_000 == 0:
                logger.info(
                    f"  {processed:,} filas procesadas — {len(military_hex):,} militares encontradas..."
                )
            if not _is_military_row(row):
                continue
            icao24 = (
                row.get("icao24", "")
                .strip()
                .upper()
                .replace("-", "")
                .replace(" ", "")
            )
            if not icao24 or len(icao24) != 6:
                continue
            try:
                int(icao24, 16)
                military_hex.add(icao24)
            except ValueError:
                pass
        logger.info(
            f"CSV procesado: {processed:,} filas totales, "
            f"{len(military_hex):,} aeronaves militares identificadas"
        )
    except Exception as exc:
        logger.error(f"Error procesando CSV: {exc}")
        return 0

    if not military_hex:
        logger.warning(
            "No se encontraron aeronaves militares en el CSV. "
            "Se conserva el archivo existente."
        )
        return 0

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as fh:
        for hex_code in sorted(military_hex):
            fh.write(f"{hex_code}\n")

    logger.info(f"military_hex.txt actualizado en {output_file} ({len(military_hex):,} entradas)")
    return len(military_hex)


def update_military_db_if_needed(
    output_file: Path,
    max_age_days: int = 30,
    min_entries: int = 1000,
) -> bool:
    """Actualiza military_hex.txt si no existe, supera max_age_days, o tiene pocas entradas.

    Args:
        output_file: Ruta del fichero de hex codes militares.
        max_age_days: Dias maximos antes de forzar una actualizacion.
        min_entries: Minimo de entradas esperadas; si el fichero tiene menos, se fuerza descarga.

    Returns:
        True si el fichero fue actualizado, False en caso contrario.
    """
    if output_file.exists():
        entry_count = sum(1 for line in output_file.read_text(encoding="utf-8").splitlines() if line.strip())
        age_days = (
            datetime.now(timezone.utc).timestamp() - output_file.stat().st_mtime
        ) / 86400
        if entry_count < min_entries:
            logger.info(
                f"military_hex.txt tiene solo {entry_count} entradas (minimo: {min_entries}) — forzando actualizacion"
            )
        elif age_days < max_age_days:
            logger.info(
                f"military_hex.txt tiene {age_days:.1f} dias de antiguedad con {entry_count:,} entradas — no requiere actualizacion"
            )
            return False
        else:
            logger.info(
                f"military_hex.txt tiene {age_days:.1f} dias ({entry_count:,} entradas) — iniciando actualizacion"
            )
    else:
        logger.info("military_hex.txt no existe — descargando por primera vez")

    count = download_and_extract_military_hex(output_file)
    return count > 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
    )
    result = download_and_extract_military_hex(config.MILITARY_HEX_FILE)
    print(f"\nResultado: {result:,} aeronaves militares en {config.MILITARY_HEX_FILE}")
    sys.exit(0 if result > 0 else 1)
