#!/usr/bin/env python3
"""
verify.py — Verificación rápida de las fases 1-6
Ejecutar: python verify.py
"""

import os
import sys
import json
import time
import hashlib
import asyncio
from datetime import datetime, timezone
from dataclasses import dataclass, field

# ── Colores en terminal ────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW= "\033[93m"
BLUE  = "\033[94m"
RESET = "\033[0m"
BOLD  = "\033[1m"

def ok(msg):    print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg):  print(f"  {RED}✗ {msg}{RESET}")
def warn(msg):  print(f"  {YELLOW}⚠ {msg}{RESET}")
def section(msg): print(f"\n{BOLD}{BLUE}▶ {msg}{RESET}")

@dataclass
class Results:
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    errors: list = field(default_factory=list)

R = Results()

def check(condition, success_msg, fail_msg, critical=False):
    if condition:
        ok(success_msg)
        R.passed += 1
    else:
        fail(fail_msg)
        R.failed += 1
        R.errors.append(fail_msg)
        if critical:
            print(f"\n  {RED}Error crítico — abortando verificación{RESET}")
            summary()
            sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# FASE 1 — BASE DE DATOS
# ══════════════════════════════════════════════════════════════════════════════
def verify_database():
    section("FASE 1 — Base de datos y modelo canónico")
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        db_url = os.getenv("DATABASE_URL", os.getenv("DB_URL", ""))
        if not db_url:
            fail("DATABASE_URL / DB_URL no definida en entorno")
            R.failed += 1
            return None

        conn = psycopg2.connect(db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        ok("Conexión a PostgreSQL establecida")
        R.passed += 1

        # Tablas obligatorias
        tablas = [
            "sources_metadata",
            "events_quarantine",
            "events_canonical",
            "incidents",
            "aoi",
            "corrections_audit",
        ]
        cur.execute("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
        """)
        existentes = {r["tablename"] for r in cur.fetchall()}

        for tabla in tablas:
            check(tabla in existentes,
                  f"Tabla '{tabla}' existe",
                  f"Tabla '{tabla}' NO existe", critical=(tabla == "events_canonical"))

        # Extensión PostGIS
        cur.execute("SELECT extname FROM pg_extension WHERE extname='postgis'")
        check(cur.fetchone() is not None,
              "Extensión PostGIS instalada",
              "PostGIS NO instalado — las queries geoespaciales fallarán", critical=True)

        # Índices geoespaciales críticos
        cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename IN ('events_canonical', 'incidents', 'aoi')
            AND indexdef ILIKE '%gist%'
        """)
        gist_indexes = cur.fetchall()
        check(len(gist_indexes) >= 3,
              f"Índices GIST encontrados: {len(gist_indexes)}",
              f"Solo {len(gist_indexes)} índices GIST (se esperan ≥3) — queries espaciales lentas")

        # Campo TIMESTAMPTZ en events_canonical
        cur.execute("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name='events_canonical' AND column_name='event_time'
        """)
        row = cur.fetchone()
        check(row and "timestamp" in row["data_type"].lower() and "time zone" in row["data_type"].lower(),
              "event_time es TIMESTAMPTZ (con zona horaria)",
              "event_time NO es TIMESTAMPTZ — riesgo de bug silencioso en UTC")

        # Enum incident_status
        cur.execute("""
            SELECT typname FROM pg_type WHERE typname='incident_status'
        """)
        check(cur.fetchone() is not None,
              "Enum 'incident_status' existe",
              "Enum 'incident_status' NO existe")

        cur.close()
        return conn

    except ImportError:
        fail("psycopg2 no instalado — ejecuta: pip install psycopg2-binary")
        R.failed += 1
        return None
    except Exception as e:
        fail(f"Error de conexión: {e}")
        R.failed += 1
        return None


# ══════════════════════════════════════════════════════════════════════════════
# FASE 2 — VALIDACIÓN Y SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════
def verify_validation():
    section("FASE 2 — Validación y schemas Pydantic")

    # Importar schema canónico
    try:
        from schemas.event_schema import EventCanonicalCreate
        ok("Schema EventCanonicalCreate importado")
        R.passed += 1
    except ImportError as e:
        fail(f"No se puede importar EventCanonicalCreate: {e}")
        R.failed += 1
        return

    # Caso OK: evento válido
    try:
        evt = EventCanonicalCreate(
            event_id_source="test-001",
            source="usgs",
            event_time=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            ingest_time=datetime.now(timezone.utc),
            event_type="earthquake",
            category="earthquake",
            latitude=47.1,
            longitude=36.8,
        )
        check(evt.event_time.tzinfo is not None,
              "event_time tiene timezone (UTC aware)",
              "event_time sin timezone — fallo en normalización UTC")
    except Exception as e:
        fail(f"EventCanonicalCreate falla con datos válidos: {e}")
        R.failed += 1

    # Importar función de validación
    try:
        from jobs.validation_job import validate_event
        ok("Función validate_event importada")
        R.passed += 1
    except ImportError as e:
        warn(f"validate_event no encontrada en jobs.validation_job: {e}")
        R.warnings += 1
        return

    casos = [
        # (payload,               rejection_code esperado, descripción)
        ({"lat": 999, "lon": 0},  "INVALID_COORDS",        "lat fuera de rango"),
        ({"lat": None, "lon": 0}, "NULL_COORDS",           "lat nulo"),
        ({"lat": 40, "lon": 200}, "INVALID_COORDS",        "lon fuera de rango"),
        ({"lat": 40, "lon": 10, "event_time": "2099-01-01T00:00:00Z"}, "FUTURE_DATE", "fecha futura"),
        ({"lat": 40, "lon": 10, "fatalities": -5}, "NEGATIVE_FATALITIES", "fatalities inválido"),
        ({},                      "SCHEMA_ERROR",          "payload vacío"),
    ]

    for payload, expected_code, desc in casos:
        try:
            result = validate_event(payload)
            if result and result.get("rejection_code") == expected_code:
                ok(f"Validación correcta: {desc}")
                R.passed += 1
            else:
                fail(f"Validación incorrecta para '{desc}' — se esperaba {expected_code}, se obtuvo: {result}")
                R.failed += 1
        except Exception as e:
            fail(f"validate_event lanzó excepción para '{desc}': {e}")
            R.failed += 1


# ══════════════════════════════════════════════════════════════════════════════
# FASE 3+4 — INGESTORES Y MAPPERS
# ══════════════════════════════════════════════════════════════════════════════
def verify_ingestors(conn):
    section("FASE 3+4 — Ingestores y mappers (USGS, FIRMS, GDELT)")

    fuentes = ["usgs", "firms", "gdelt"]

    for fuente in fuentes:
        # Comprobar que existe el ingestor
        try:
            mod = __import__(f"ingestors.{fuente}_ingestor", fromlist=["*"])
            ok(f"Módulo ingestors/{fuente}_ingestor.py importado")
            R.passed += 1
        except ImportError:
            fail(f"ingestors/{fuente}_ingestor.py no encontrado")
            R.failed += 1
            continue

        # Comprobar que existe el mapper
        try:
            mod = __import__(f"normalizers.{fuente}_mapper", fromlist=["*"])
            ok(f"Módulo normalizers/{fuente}_mapper.py importado")
            R.passed += 1
        except ImportError:
            fail(f"normalizers/{fuente}_mapper.py no encontrado")
            R.failed += 1

    if conn is None:
        warn("Sin conexión a BD — saltando verificación de datos reales")
        R.warnings += 1
        return

    cur = conn.cursor()

    # Verificar que hay datos en BD por fuente
    for fuente in fuentes:
        cur.execute(
            "SELECT COUNT(*) as c FROM events_canonical WHERE source = %s",
            (fuente,)
        )
        count = cur.fetchone()[0]
        check(count > 0,
              f"{fuente.upper()}: {count} eventos en events_canonical",
              f"{fuente.upper()}: 0 eventos — ingestor no ha corrido o falla")

    # Verificar que todos los event_time son UTC (sin offset distinto a +00)
    cur.execute("""
        SELECT COUNT(*) FROM events_canonical
        WHERE extract(timezone FROM event_time) != 0
    """)
    non_utc = cur.fetchone()[0]
    check(non_utc == 0,
          "Todos los event_time están en UTC",
          f"{non_utc} registros con event_time fuera de UTC — bug en normalización")

    # Verificar que no hay coordenadas imposibles en BD (no debería haber si validación funciona)
    cur.execute("""
        SELECT COUNT(*) FROM events_canonical
        WHERE ST_X(location_point) NOT BETWEEN -180 AND 180
           OR ST_Y(location_point) NOT BETWEEN -90 AND 90
    """)
    bad_coords = cur.fetchone()[0]
    check(bad_coords == 0,
          "Sin coordenadas inválidas en events_canonical",
          f"{bad_coords} registros con coordenadas inválidas — validación no filtra correctamente")

    # Verificar deduplicación: no debe haber (source, event_id_source) duplicados
    cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT source, event_id_source, COUNT(*) as c
            FROM events_canonical
            GROUP BY source, event_id_source
            HAVING COUNT(*) > 1
        ) dups
    """)
    dups = cur.fetchone()[0]
    check(dups == 0,
          "Sin duplicados (source, event_id_source)",
          f"{dups} pares (source, event_id_source) duplicados — bug en deduplicación")

    cur.close()


# ══════════════════════════════════════════════════════════════════════════════
# FASE 5 — CLUSTERING E INCIDENTES
# ══════════════════════════════════════════════════════════════════════════════
def verify_clustering(conn):
    section("FASE 5 — Clustering e incidentes")

    try:
        from jobs.clustering_job import run_clustering_job
        ok("Job clustering_job importado")
        R.passed += 1
    except ImportError as e:
        fail(f"jobs/clustering_job.py no encontrado: {e}")
        R.failed += 1

    try:
        from jobs.incident_lifecycle_job import run_lifecycle_job
        ok("Job incident_lifecycle_job importado")
        R.passed += 1
    except ImportError as e:
        fail(f"jobs/incident_lifecycle_job.py no encontrado: {e}")
        R.failed += 1

    if conn is None:
        warn("Sin conexión a BD — saltando verificación de datos de incidentes")
        R.warnings += 1
        return

    cur = conn.cursor()

    # Hay incidentes creados
    cur.execute("SELECT COUNT(*) FROM incidents")
    total = cur.fetchone()[0]
    check(total > 0,
          f"{total} incidentes en BD",
          "0 incidentes — el job de clustering no ha corrido o no agrupa nada")

    # Incidentes con status válido
    cur.execute("""
        SELECT COUNT(*) FROM incidents
        WHERE status NOT IN ('open','updated','stale','closed','false_positive')
    """)
    bad_status = cur.fetchone()[0]
    check(bad_status == 0,
          "Todos los incidentes tienen status válido",
          f"{bad_status} incidentes con status inválido")

    # Severidad en rango [0, 10]
    cur.execute("""
        SELECT COUNT(*) FROM incidents
        WHERE severity_max NOT BETWEEN 0 AND 10
           OR severity_latest NOT BETWEEN 0 AND 10
    """)
    bad_sev = cur.fetchone()[0]
    check(bad_sev == 0,
          "Severidades en rango [0–10]",
          f"{bad_sev} incidentes con severidad fuera de rango")

    # Regla D11: fatalities_total no debería superar el máximo de sus eventos
    # (verificación aproximada: ningún incidente con 1 fuente y fatalities absurdos)
    cur.execute("""
        SELECT COUNT(*) FROM incidents
        WHERE source_count = 1 AND fatalities_total > 10000
    """)
    absurd = cur.fetchone()[0]
    check(absurd == 0,
          "Sin valores absurdos en fatalities_total (posible suma en vez de MAX)",
          f"{absurd} incidentes con fatalities sospechosamente altos (¿usas SUM en vez de MAX?)")

    # Incidentes sin canonical_point (no debería ocurrir)
    cur.execute("SELECT COUNT(*) FROM incidents WHERE canonical_point IS NULL")
    no_point = cur.fetchone()[0]
    check(no_point == 0,
          "Todos los incidentes tienen canonical_point",
          f"{no_point} incidentes sin canonical_point")

    # Distribución de estados (informativo)
    cur.execute("""
        SELECT status, COUNT(*) as c FROM incidents GROUP BY status ORDER BY c DESC
    """)
    rows = cur.fetchall()
    print(f"    {'Estados de incidentes':30s}", end="")
    for status, count in rows:
        print(f"  {status}={count}", end="")
    print()

    cur.close()


# ══════════════════════════════════════════════════════════════════════════════
# FASE 6 — API
# ══════════════════════════════════════════════════════════════════════════════
def verify_api():
    section("FASE 6 — API FastAPI")
    try:
        import httpx
    except ImportError:
        warn("httpx no instalado — saltando tests de API. Instalar: pip install httpx")
        R.warnings += 1
        return

    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")

    try:
        # Health check
        r = httpx.get(f"{base_url}/health", timeout=5)
        check(r.status_code == 200,
              f"GET /health → 200 OK",
              f"GET /health → {r.status_code} (¿está corriendo la API?)")
    except Exception as e:
        fail(f"No se puede conectar a {base_url}: {e}")
        fail("Asegúrate de que la API está corriendo antes de ejecutar verify.py")
        R.failed += 2
        return

    # Sin auth → 401
    try:
        r = httpx.get(f"{base_url}/v1/incidents", timeout=5)
        check(r.status_code == 401,
              "GET /v1/incidents sin auth → 401 Unauthorized",
              f"GET /v1/incidents sin auth → {r.status_code} (debería ser 401)")
    except Exception as e:
        fail(f"Error al llamar /v1/incidents: {e}")
        R.failed += 1

    # bbox inválido → 422
    token = os.getenv("TEST_JWT_TOKEN", "")
    if token:
        headers = {"Authorization": f"Bearer {token}"}
        try:
            r = httpx.get(f"{base_url}/v1/incidents?bbox=invalid", headers=headers, timeout=5)
            check(r.status_code == 422,
                  "GET /v1/incidents?bbox=invalid → 422 Unprocessable",
                  f"GET /v1/incidents?bbox=invalid → {r.status_code} (debería ser 422)")

            # Respuesta con datos reales
            r = httpx.get(f"{base_url}/v1/incidents?limit=5", headers=headers, timeout=5)
            check(r.status_code == 200,
                  "GET /v1/incidents con auth → 200 OK",
                  f"GET /v1/incidents con auth → {r.status_code}")

            if r.status_code == 200:
                data = r.json()
                check("total" in data and "incidents" in data,
                      f"Respuesta tiene campos 'total' e 'incidents' ({data.get('total',0)} incidentes)",
                      "Respuesta malformada — faltan campos 'total' o 'incidents'")

                # Verificar que no hay campos sensibles expuestos
                if data.get("incidents"):
                    inc = data["incidents"][0]
                    check("hex" not in inc and "mmsi" not in inc,
                          "Sin campos sensibles (hex ADS-B, MMSI) en respuesta pública",
                          "Campo sensible expuesto en API pública (hex o mmsi)")

        except Exception as e:
            fail(f"Error en tests con auth: {e}")
            R.failed += 1
    else:
        warn("TEST_JWT_TOKEN no definido — saltando tests con autenticación")
        warn("Define TEST_JWT_TOKEN=<tu_token> para tests completos de API")
        R.warnings += 2

    # Rate limiting (test básico)
    try:
        responses = [httpx.get(f"{base_url}/health", timeout=2) for _ in range(5)]
        all_ok = all(r.status_code in (200, 429) for r in responses)
        check(all_ok,
              "Rate limiting responde correctamente (200 o 429)",
              "Respuestas inesperadas en test de rate limiting")
    except Exception:
        pass  # No crítico


# ══════════════════════════════════════════════════════════════════════════════
# RESUMEN FINAL
# ══════════════════════════════════════════════════════════════════════════════
def summary():
    total = R.passed + R.failed
    print(f"\n{'━'*55}")
    print(f"{BOLD}  RESULTADO FINAL{RESET}")
    print(f"{'━'*55}")
    print(f"  {GREEN}Pasados  : {R.passed}{RESET}")
    print(f"  {RED}Fallados : {R.failed}{RESET}")
    print(f"  {YELLOW}Avisos   : {R.warnings}{RESET}")
    print(f"  Total    : {total}")

    if R.errors:
        print(f"\n{BOLD}  Errores a resolver:{RESET}")
        for i, e in enumerate(R.errors, 1):
            print(f"  {RED}{i}. {e}{RESET}")

    print(f"{'━'*55}")

    if R.failed == 0:
        print(f"\n  {GREEN}{BOLD}✓ Todo correcto — puedes pasar a Fase 7{RESET}\n")
    elif R.failed <= 3:
        print(f"\n  {YELLOW}{BOLD}⚠ Hay {R.failed} problema(s) menor(es) — revisar antes de continuar{RESET}\n")
    else:
        print(f"\n  {RED}{BOLD}✗ {R.failed} problemas — NO continuar a Fase 7 hasta resolver{RESET}\n")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n{BOLD}{'━'*55}")
    print(f"  VERIFICACIÓN FASES 1–6")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'━'*55}{RESET}")

    conn = verify_database()
    verify_validation()
    verify_ingestors(conn)
    verify_clustering(conn)
    verify_api()

    if conn:
        conn.close()

    summary()