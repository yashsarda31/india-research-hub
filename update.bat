@echo off
rem Refresh: run every scraper, download new PDFs, rebuild site/data.js.
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" build\update.py %*
pause
