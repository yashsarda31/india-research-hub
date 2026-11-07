@echo off
rem Serve the site at http://127.0.0.1:8790/site/ and open it.
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%PY%" set "PY=python"
start "" http://127.0.0.1:8790/site/
"%PY%" -m http.server 8790 --bind 127.0.0.1
