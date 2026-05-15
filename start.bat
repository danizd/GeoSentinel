@echo off
title GeoSentinel

echo =====================================
echo  GeoSentinel - Arranque del sistema
echo =====================================
echo.

REM Cargar variables de entorno desde .env
if not exist ".env" (
    echo ERROR: No se encuentra el archivo .env en la raiz del proyecto.
    pause
    exit /b 1
)
echo [1/6] Cargando variables de entorno...
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" set "%%A=%%B"
)
echo       OK

REM Levantar contenedor PostgreSQL si no esta corriendo
echo [2/6] Levantando base de datos...
docker compose up -d
if errorlevel 1 (
    echo ERROR: No se pudo levantar el contenedor PostgreSQL.
    echo        Asegurate de que Docker Desktop esta iniciado.
    pause
    exit /b 1
)
echo       Esperando a que PostgreSQL este listo...
:waitdb
uv run python backend\scripts\check_db.py
if errorlevel 1 (
    timeout /t 2 /nobreak > nul
    goto waitdb
)
echo       BD lista.

REM Liberar puertos si hay instancias previas
echo [3/6] Liberando puertos...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo       Matando proceso previo en puerto 8000 ^(PID %%P^)...
    taskkill /PID %%P /F > nul 2>&1
)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8002 " ^| findstr "LISTENING"') do (
    echo       Matando proceso previo en puerto 8002 ^(PID %%P^)...
    taskkill /PID %%P /F > nul 2>&1
)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8003 " ^| findstr "LISTENING"') do (
    echo       Matando proceso previo en puerto 8003 ^(PID %%P^)...
    taskkill /PID %%P /F > nul 2>&1
)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    echo       Matando proceso previo en puerto 5173 ^(PID %%P^)...
    taskkill /PID %%P /F > nul 2>&1
)
echo       OK

REM Arrancar Relay Militar en ventana separada
echo [4/6] Arrancando Relay Militar ^(OpenSky^)...
start "GeoSentinel Relay" cmd /c "cd /d %~dp0 && start_relay.bat"

REM Esperar a que el relay este disponible
timeout /t 3 /nobreak > nul
curl -s http://localhost:8002/docs > nul 2>&1
if errorlevel 1 (
    echo WARNING: El relay militar no esta respondiendo.
    echo          Verifica las credenciales de OpenSky en .env
    echo          El sistema continuara sin tracks militares.
)

REM Arrancar Relay AIS en ventana separada
echo [5/6] Arrancando Relay AIS...
start "GeoSentinel AIS" cmd /c "cd /d %~dp0 && set PYTHONPATH=%~dp0&& python -m services.ais_relay.main"

timeout /t 2 /nobreak > nul
curl -s http://localhost:8003/docs > nul 2>&1
if errorlevel 1 (
    echo WARNING: El relay AIS no esta respondiendo.
    echo          El sistema continuara sin datos de buques.
)

echo [6/6] Arrancando Frontend...
start "" /b cmd /c "cd /d %~dp0frontend && npm run dev"
echo       OK

echo.
echo =====================================
echo  GeoSentinel iniciado:
echo       Backend: http://localhost:8000
echo       Swagger:  http://localhost:8000/docs
echo       Frontend: http://localhost:5173
echo       Relay:    http://localhost:8002
echo       AIS:      http://localhost:8003
echo =====================================
echo.
echo  Para detener todos los servicios, cierra las ventanas
echo  o usa Ctrl+C en cada una.
echo.

echo Arrancando API en esta consola...
echo.

uv run uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
