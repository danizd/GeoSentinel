@echo off
title GeoSentinel - Reparar Docker Desktop

echo =====================================
echo  Reparando Docker Desktop bloqueado
echo =====================================
echo.

echo [1/4] Matando procesos Docker...
powershell -NoProfile -Command "Get-Process -Name '*docker*','com.docker.*' -ErrorAction SilentlyContinue | Stop-Process -Force"

echo [2/4] Apagando WSL...
wsl --shutdown

echo [3/4] Esperando 5 segundos...
timeout /t 5 /nobreak > nul

echo [4/4] Arrancando Docker Desktop...
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
) else (
    echo ERROR: No se encuentra Docker Desktop en %ProgramFiles%\Docker\Docker\
    pause
    exit /b 1
)

echo.
echo =====================================
echo  Docker Desktop arrancando.
echo  Espera ~60 segundos hasta que el icono
echo  de la barra de tareas muestre "Engine running"
echo  antes de ejecutar start.bat o ingest.bat
echo =====================================
pause
