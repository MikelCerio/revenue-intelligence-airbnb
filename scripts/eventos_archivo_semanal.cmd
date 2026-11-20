@echo off
rem Lanzador de la tarea programada semanal: archivo histórico de eventos de Kulturklik.
rem La API solo conserva unos 5 meses hacia atrás; si no se ejecuta cada semana, se pierden eventos.
rem Actualiza eventos\eventos_euskadi.csv, eventos_cambios.csv y capturas.csv.
rem La salida se acumula en datos\raw\_logs\eventos.log (ignorado por Git).
set "REPO=%~dp0.."
if not exist "%REPO%\datos\raw\_logs" mkdir "%REPO%\datos\raw\_logs"
set "PYTHONIOENCODING=utf-8"
echo ===== %date% %time% >> "%REPO%\datos\raw\_logs\eventos.log"
"%REPO%\.venv\Scripts\python.exe" "%REPO%\scripts\eventos_archivo.py" >> "%REPO%\datos\raw\_logs\eventos.log" 2>&1
echo exit %errorlevel% >> "%REPO%\datos\raw\_logs\eventos.log"
exit /b %errorlevel%
