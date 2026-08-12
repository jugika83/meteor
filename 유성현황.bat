@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PY=C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe
if not exist "%PY%" set PY=python
"%PY%" "유성현황.py" %*
if errorlevel 1 pause
