@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m venv .venv
  goto check
)
where python >nul 2>nul
if not errorlevel 1 (
  python -m venv .venv
  goto check
)
echo Install Python 3.10 or newer from python.org and enable Add Python to PATH.
pause
exit /b 1
:check
if not exist ".venv\Scripts\python.exe" (
  echo Failed to create Python environment.
  pause
  exit /b 1
)
:install
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Installation failed. Check your internet connection.
  pause
  exit /b 1
)
if not exist .env copy .env.example .env >nul
echo Ready. Set TELEGRAM_BOT_TOKEN in .env and run start.bat.
pause
