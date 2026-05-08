@echo off
title GeoSentinel - Ingesta

echo ===================================
echo  GeoSentinel - Obtener datos reales
echo ===================================
echo.

REM Cargar variables de entorno desde .env
if not exist ".env" (
    echo ERROR: No se encuentra .env
    pause
    exit /b 1
)
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" set "%%A=%%B"
)

REM Verificar que PostgreSQL esta listo
echo Verificando disponibilidad de la base de datos...
:waitdb
uv run python scripts\check_db.py
if errorlevel 1 (
    echo   BD no disponible en localhost:5432, esperando 3 segundos...
    timeout /t 3 /nobreak > nul
    goto waitdb
)
echo   BD lista.
echo.

REM Aplicar migraciones (idempotente)
echo [1/5] Aplicando migraciones de BD...
uv run alembic upgrade head
if errorlevel 1 (
    echo ERROR: Fallo alembic upgrade.
    pause
    exit /b 1
)

REM Seed sources_metadata (idempotente)
echo [2/5] Sembrando sources_metadata...
uv run python scripts\run_seed.py
if errorlevel 1 (
    echo ERROR: Fallo el seed.
    pause
    exit /b 1
)

REM Ingestor USGS
echo [3/5] Descargando terremotos USGS...
uv run python scripts\run_usgs.py
if errorlevel 1 (
    echo ERROR: Fallo el ingestor USGS.
    pause
    exit /b 1
)

REM Clustering
echo [4/5] Ejecutando clustering...
uv run python scripts\run_clustering.py
if errorlevel 1 (
    echo ERROR: Fallo el clustering.
    pause
    exit /b 1
)

REM Abrir navegador
echo [5/5] Listo. Abriendo Swagger UI...
echo.
echo   http://localhost:8000/docs
echo   http://localhost:8000/v1/incidents
echo.
start "" "http://localhost:8000/docs"
pause
