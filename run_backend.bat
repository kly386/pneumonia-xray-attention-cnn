@echo off
cd /d "%~dp0"

if not exist ".backend-venv\python.exe" (
  echo [ERROR] .backend-venv\python.exe not found.
  echo Create the backend virtual environment first.
  pause
  exit /b 1
)

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo Starting PNEUMO-AI backend on http://127.0.0.1:18080 ...
echo Keep this window open while using the frontend.
echo.

".backend-venv\python.exe" -m uvicorn src.backend.main:app --host 127.0.0.1 --port 18080 --reload

echo.
echo [ERROR] Backend stopped. Check the messages above.
pause
