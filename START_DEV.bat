@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title KisanMausam - Developer mode (hot reload)
if not exist "node_modules" call npm install
if not exist ".venv\Scripts\python.exe" py -m venv .venv
if not exist ".venv\.requirements-installed" ( call ".venv\Scripts\python.exe" -m pip install -r server\requirements-dev.txt & echo installed>".venv\.requirements-installed" )
start "KisanMausam API" /D "%~dp0" cmd /k "".venv\Scripts\python.exe" -m uvicorn server.main:app --reload --host 127.0.0.1 --port 8000"
start "KisanMausam Web (Vite)" /D "%~dp0" cmd /k "npm run dev"
timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:5173"
