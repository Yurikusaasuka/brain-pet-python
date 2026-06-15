@echo off
cd /d "%~dp0"
where pythonw >nul 2>&1
if %ERRORLEVEL% == 0 (
    start "" pythonw main.py
) else (
    python main.py
)
exit
