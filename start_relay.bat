@echo off
REM Cargar variables de entorno desde .env
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" set "%%A=%%B"
)
set PYTHONPATH=%~dp0;%PYTHONPATH%
cd %~dp0
python -m services.military_relay.main