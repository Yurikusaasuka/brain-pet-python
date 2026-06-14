@echo off
cd /d "%~dp0"
set PYTHONW=C:\Users\qmxyh\.conda\envs\brain-pet\pythonw.exe
if exist "%PYTHONW%" (
    start "" "%PYTHONW%" main.py
) else (
    start "" /B C:\Users\qmxyh\.conda\envs\brain-pet\python.exe main.py
)
exit
