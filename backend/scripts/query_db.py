import os
from sqlalchemy import create_engine, text

engine = create_engine(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel"))
conn = engine.connect()

print("=" * 60)
print("GEO SENTINEL — Consultas Rápidas")
print("=" * 60)

print("\n1. Eventos por fuente")
print("-" * 40)
result = conn.execute(text("SELECT source, COUNT(*) as eventos FROM events_canonical GROUP BY source"))
for row in result:
    print(f"  {row[0]:15} {row[1]:>6}")

print("\n2. Eventos sin incidente")
print("-" * 40)
result = conn.execute(text("""
    SELECT COUNT(*) as sin_incidente
    FROM events_canonical
    WHERE id NOT IN (
        SELECT UNNEST(linked_event_ids) FROM incidents WHERE linked_event_ids IS NOT NULL
    )
"""))
print(f"  {result.scalar()}")

print("\n3. Eventos en quarantine por código de rechazo")
print("-" * 40)
result = conn.execute(text("SELECT rejection_code, COUNT(*) FROM events_quarantine GROUP BY rejection_code"))
rows = result.fetchall()
if rows:
    for row in rows:
        print(f"  {row[0]:20} {row[1]:>6}")
else:
    print("  (vacío)")

print("\n4. Último evento USGS")
print("-" * 40)
result = conn.execute(text("SELECT MAX(event_time), MAX(ingest_time) FROM events_canonical WHERE source = 'usgs'"))
row = result.fetchone()
print(f"  event_time:  {row[0]}")
print(f"  ingest_time:  {row[1]}")

print("\n5. Incidentes por estado")
print("-" * 40)
result = conn.execute(text("SELECT status, COUNT(*) FROM incidents GROUP BY status"))
for row in result:
    print(f"  {row[0]:15} {row[1]:>6}")

print("\n6. Totales generales")
print("-" * 40)
for table in ["events_canonical", "events_quarantine", "incidents", "aoi"]:
    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
    print(f"  {table:20} {result.scalar():>6}")

print("\n7. Eventos dentro de incidentes")
print("-" * 40)
result = conn.execute(text("""
    SELECT e.source, e.event_time, e.event_type,
           ST_Y(e.location_point) as lat,
           ST_X(e.location_point) as lon,
           i.incident_id
    FROM events_canonical e
    JOIN incidents i ON e.id = ANY(i.linked_event_ids)
    LIMIT 5
"""))
for row in result:
    print(f"  {row[0]:10} {str(row[1]):28} {row[2]:15} lat={row[3]:.4f} lon={row[4]:.4f}")
    print(f"           incident: {row[5]}")

print("\n8. Estadísticas eventos USGS")
print("-" * 40)
result = conn.execute(text("""
    SELECT
      MIN(event_time) as primer_evento,
      MAX(event_time) as ultimo_evento,
      COUNT(DISTINCT DATE(event_time)) as dias_distintos,
      AVG(ST_Y(location_point)) as lat_media,
      STDDEV(ST_X(location_point)) as lon_dispersion,
      COUNT(*) as total
    FROM events_canonical
    WHERE source = 'usgs'
"""))
row = result.fetchone()
print(f"  primer_evento:    {row[0]}")
print(f"  ultimo_evento:     {row[1]}")
print(f"  dias_distintos:    {row[2]}")
print(f"  lat_media:         {row[3]:.4f}" if row[3] else "  lat_media:         N/A")
print(f"  lon_dispersion:    {row[4]:.4f}" if row[4] else "  lon_dispersion:    N/A")
print(f"  total:             {row[5]}")

print("\n" + "=" * 60)
conn.close()
