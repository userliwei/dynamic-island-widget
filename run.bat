@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   DynamicIsland - Desktop Widget
echo ==========================================
echo.

where pythonw >nul 2>&1
if errorlevel 1 goto NO_PYTHON

echo Starting...
start "" pythonw "main.py"
timeout /t 4 >nul

tasklist /FI "IMAGENAME eq pythonw.exe" 2>nul | find /i "pythonw.exe" >nul
if errorlevel 1 goto FAILED

echo.
echo [OK] DynamicIsland is running.
echo Look at the top-center of your screen, or the system tray.
echo.
timeout /t 3 >nul
exit /b 0

:NO_PYTHON
echo [ERROR] pythonw.exe not found in PATH.
echo Please install Python 3 and make sure it is added to PATH.
echo.
pause
exit /b 1

:FAILED
echo.
echo [ERROR] Failed to start. See log:
echo   %%USERPROFILE%%\.dynamic_island\error.log
echo.
pause
exit /b 1
