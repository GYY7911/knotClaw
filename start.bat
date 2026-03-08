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
echo   [1] Start Web Server (auto clean cache)
echo   [2] Start CLI Mode
echo   [3] Stop Server
echo   [4] Clean Cache Only
echo   [5] Restart Server (stop+clean+start)
echo   [6] Exit
echo.
echo   Status:
netstat -an | findstr ":9090.*LISTENING" >nul 2>&1
if errorlevel 1 (
    echo   - Server: NOT running
) else (
    echo   - Server: Running at http://localhost:9090
)
echo.
set /p choice=   Select [1-6]:

if "%choice%"=="1" goto start_web
if "%choice%"=="2" goto start_cli
if "%choice%"=="3" goto stop
if "%choice%"=="4" goto clean
if "%choice%"=="5" goto restart
if "%choice%"=="6" exit
goto menu

:start_web
cls
echo.
echo   [Start Web Server]
echo.

cd /d "%~dp0"

REM 设置端口（如果8080被占用可改为其他端口）
set PORT=9090

echo   [1/3] Cleaning Python cache...
for /d /r %%i in (__pycache__) do @if exist "%%i" rd /s /q "%%i"
del /s /q *.pyc >nul 2>&1
if exist temp rd /s /q temp 2>nul
echo        Done

echo   [2/3] Checking dependencies...
python -c "import flask; print('        OK')" >nul 2>&1
if errorlevel 1 (
    echo        Installing Flask...
    pip install flask -q
)

echo   [3/3] Starting web server...
echo.
echo   ========================================
echo   Server: http://localhost:%PORT%
echo   Press Ctrl+C to stop
echo   ========================================
echo.

python -m src.main --web --port %PORT%
pause
exit

:start_cli
cls
echo.
echo   [Start CLI Mode]
echo.

cd /d "%~dp0"

echo   Starting interactive CLI...
echo.

python -m src.main
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

REM 设置端口
set PORT=9090

echo   [2/4] Cleaning cache...
for /d /r %%i in (__pycache__) do @if exist "%%i" rd /s /q "%%i"
del /s /q *.pyc >nul 2>&1
if exist temp rd /s /q temp 2>nul
echo        Done

echo   [3/4] Checking dependencies...
python -c "import flask; print('        OK')" >nul 2>&1
if errorlevel 1 (
    echo        Installing Flask...
    pip install flask -q
)

echo   [4/4] Starting web server...
echo.
echo   ========================================
echo   Server: http://localhost:%PORT%
echo   Press Ctrl+C to stop
echo   ========================================
echo.

python -m src.main --web --port %PORT%
pause
exit
