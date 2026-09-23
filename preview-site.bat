@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup.bat first, or use open-site.bat without Python.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8765 in your browser. Keep this window open.
".venv\Scripts\python.exe" serve_site.py
pause
