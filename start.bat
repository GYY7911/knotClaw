@echo off
chcp 65001 >nul 2>&1
title Knotclaw Control Panel

:menu
cls
echo.
echo   ========================================
echo          Knotclaw Control Panel
echo   ========================================
echo.
echo   [1] Start Server (auto clean cache)
echo   [2] Stop Server
echo   [3] Clean Cache Only
echo   [4] Restart Server (stop+clean+start)
echo   [5] Exit
echo.
echo   Status:
netstat -an | findstr ":8088.*LISTENING" >nul 2>&1
if errorlevel 1 (
    echo   - Server: NOT running
) else (
    echo   - Server: Running at http://localhost:8088
)
echo.
set /p choice=   Select [1-5]:

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto clean
if "%choice%"=="4" goto restart
if "%choice%"=="5" exit
goto menu

:start
cls
echo.
echo   [Start Server]
echo.

cd /d "%~dp0"

echo   [1/3] Cleaning Python cache...
for /d /r %%i in (__pycache__) do @if exist "%%i" rd /s /q "%%i"
del /s /q *.pyc >nul 2>&1
if exist temp rd /s /q temp 2>nul
echo        Done

echo   [2/3] Checking dependencies...
python -c "import selenium; import bs4; print('        OK')" >nul 2>&1
if errorlevel 1 (
    echo        Installing...
    pip install selenium webdriver-manager beautifulsoup4 -q
)

echo   [3/3] Starting server...
echo.
echo   ========================================
echo   Server: http://localhost:8088
echo   Press Ctrl+C to stop
echo   ========================================
echo.

python simple_web.py
pause
exit

:stop
cls
echo.
echo   [Stop Server]
echo.
echo   Stopping Python processes...
taskkill /F /IM python.exe >nul 2>&1
echo        Done
echo.
pause
goto menu

:clean
cls
echo.
echo   [Clean Cache]
echo.
cd /d "%~dp0"

echo   Cleaning __pycache__...
for /d /r %%i in (__pycache__) do @if exist "%%i" rd /s /q "%%i"

echo   Cleaning .pyc files...
del /s /q *.pyc >nul 2>&1

echo   Cleaning temp folder...
if exist temp rd /s /q temp 2>nul

echo.
echo        Cache cleaned
echo.
pause
goto menu

:restart
cls
echo.
echo   [Restart Server]
echo.
echo   [1/4] Stopping server...
taskkill /F /IM python.exe >nul 2>&1
echo        Done

cd /d "%~dp0"

echo   [2/4] Cleaning cache...
for /d /r %%i in (__pycache__) do @if exist "%%i" rd /s /q "%%i"
del /s /q *.pyc >nul 2>&1
if exist temp rd /s /q temp 2>nul
echo        Done

echo   [3/4] Checking dependencies...
python -c "import selenium; import bs4; print('        OK')" >nul 2>&1
if errorlevel 1 (
    echo        Installing...
    pip install selenium webdriver-manager beautifulsoup4 -q
)

echo   [4/4] Starting server...
echo.
echo   ========================================
echo   Server: http://localhost:8088
echo   Press Ctrl+C to stop
echo   ========================================
echo.

python simple_web.py
pause
exit
