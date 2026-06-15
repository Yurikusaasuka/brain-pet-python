@echo off
cd /d "%~dp0"

where pythonw >nul 2>&1
if %ERRORLEVEL% == 0 (
    start "" pythonw main.py
    exit
)

where python >nul 2>&1
if %ERRORLEVEL% == 0 (
    python main.py
    exit
)

echo.
echo [ERROR] Python not found in PATH.
echo Please install Python from https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation.
echo Then run:  pip install -r requirements.txt
echo.
pause
