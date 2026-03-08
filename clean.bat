@echo off
chcp 65001 >nul 2>&1
echo.
echo   [Clean Knotclaw Cache]
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