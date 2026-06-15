@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set PYTHON_EXE=

:: Try each python in PATH; pick first one that has (or can install) deps
for /f "tokens=*" %%P in ('where python 2^>nul') do (
    if not defined PYTHON_EXE (
        "%%P" -c "import PIL" >nul 2>&1
        if !ERRORLEVEL! == 0 (
            set PYTHON_EXE=%%P
        ) else (
            echo Installing dependencies with %%P ...
            "%%P" -m pip install -r requirements.txt >nul 2>&1
            "%%P" -c "import PIL" >nul 2>&1
            if !ERRORLEVEL! == 0 (
                set PYTHON_EXE=%%P
            )
        )
    )
)

:: No working Python found
if not defined PYTHON_EXE (
    where python >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo.
        echo [ERROR] Python not found.
        echo Install from https://www.python.org/downloads/
        echo Check "Add Python to PATH" during installation.
    ) else (
        echo.
        echo [ERROR] Could not install dependencies automatically.
        echo Please run:  pip install -r requirements.txt
    )
    echo.
    pause
    exit /b 1
)

:: Launch without console window (pythonw), fallback to python
set PYTHONW_EXE=%PYTHON_EXE:python.exe=pythonw.exe%
if exist "%PYTHONW_EXE%" (
    start "" "%PYTHONW_EXE%" main.py
) else (
    start "" "%PYTHON_EXE%" main.py
)
