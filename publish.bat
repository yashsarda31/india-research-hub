@echo off
rem Push the public, links-only copy of the current site to GitHub Pages.
rem To refresh the data first and then publish, run:  update.bat --publish
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" build\publish_pages.py %*
pause
