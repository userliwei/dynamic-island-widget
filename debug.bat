@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   DynamicIsland - DEBUG MODE
echo   (console window shows all errors)
echo ==========================================
echo.

where python >nul 2>&1
if errorlevel 1 goto NO_PYTHON

python -c "import PyQt5" 2>nul
if errorlevel 1 (
    echo PyQt5 not found, installing...
    python -m pip install PyQt5 psutil pycaw
    echo.
)

python "main.py"
echo.
echo ==========================================
echo Program exited. Check messages above.
echo ==========================================
pause
exit /b 0

:NO_PYTHON
echo [ERROR] python.exe not found in PATH.
pause
exit /b 1
