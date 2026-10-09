@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Setting up Python environment...
  python -m venv .venv
  if errorlevel 1 goto failure
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt -c requirements-lock.txt
  if errorlevel 1 goto failure
)
if not exist "frontend\dist\index.html" (
  echo Frontend is not built. See README.md for build instructions.
  goto failure
)
".venv\Scripts\python.exe" -m backend.launch
if errorlevel 1 goto failure
exit /b 0
:failure
echo Could not start. See README.md. Python 3.12 or newer is required.
pause
exit /b 1
