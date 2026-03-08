@echo off
echo.
echo   [Stop Knotclaw Server]
echo.
echo   Stopping Python processes...
taskkill /F /IM python.exe >nul 2>&1
echo        Done
echo.
pause