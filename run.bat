@echo off
echo Starting Hadaf Al Nasar Application...
echo.

REM Set environment variables
set FLASK_APP=wsgi.py
set FLASK_DEBUG=1

REM Clear Python cache
echo Cleaning Python cache...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc 2>nul

echo Starting Flask...
echo.
flask run --debug
pause
