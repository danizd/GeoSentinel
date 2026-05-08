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
echo [1/3] Cargando variables de entorno...
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" set "%%A=%%B"
)
echo       OK

REM Levantar contenedor PostgreSQL si no esta corriendo
echo [2/3] Levantando base de datos...
docker compose up -d
if errorlevel 1 (
    echo ERROR: No se pudo levantar el contenedor PostgreSQL.
    echo        Asegurate de que Docker Desktop esta iniciado.
    pause
    exit /b 1
)
echo       Esperando a que PostgreSQL este listo...
:waitdb
uv run python scripts\check_db.py
if errorlevel 1 (
    timeout /t 2 /nobreak > nul
    goto waitdb
)
echo       BD lista.

REM Liberar puerto 8000 si hay una instancia previa
echo [3/3] Arrancando API...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo       Matando proceso previo en puerto 8000 ^(PID %%P^)...
    taskkill /PID %%P /F > nul 2>&1
)
echo.
echo       http://localhost:8000
echo       http://localhost:8000/docs  ^(Swagger UI^)
echo.
echo  Pulsa Ctrl+C para detener el servidor
echo =====================================
echo.
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
if errorlevel 1 (
    echo.
    echo ERROR: Fallo al arrancar uvicorn. Revisa el mensaje anterior.
)
echo.
pause
