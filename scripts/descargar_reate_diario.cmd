@echo off
rem Lanzador de la tarea programada diaria: foto de REATE y Alojamientos de Euskadi.
rem La salida se acumula en datos\raw\_logs\reate.log (ignorado por Git).
set "REPO=%~dp0.."
if not exist "%REPO%\datos\raw\_logs" mkdir "%REPO%\datos\raw\_logs"
set "PYTHONIOENCODING=utf-8"
echo ===== %date% %time% >> "%REPO%\datos\raw\_logs\reate.log"
"%REPO%\.venv\Scripts\python.exe" "%REPO%\scripts\descargar_reate.py" >> "%REPO%\datos\raw\_logs\reate.log" 2>&1
echo exit %errorlevel% >> "%REPO%\datos\raw\_logs\reate.log"
exit /b %errorlevel%
