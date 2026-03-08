@echo off
cd /d "%~dp0"
echo Starting Knotclaw Web Server...
echo.
echo Server: http://localhost:9090
echo Press Ctrl+C to stop
echo.
python -m src.main --web --port 9090
pause
