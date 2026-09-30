@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title KisanMausam - One Click Start
color 0A

echo.
echo ========================================================
echo              KisanMausam - One Click Start
echo ========================================================
echo.

where node >nul 2>&1 || goto NONODE
where npm  >nul 2>&1 || goto NONPM

rem ----------------------------------------------------------
rem Pick a usable Python executable. Prefer the project's venv.
rem This avoids requiring the Windows "py" launcher.
rem ----------------------------------------------------------
set "PYEXE=%~dp0.venv\Scripts\python.exe"
if exist "%PYEXE%" goto PYREADY

where python >nul 2>&1
if not errorlevel 1 (
  set "PYBASE=python"
  goto MAKEVENV
)
where py >nul 2>&1
if not errorlevel 1 (
  set "PYBASE=py"
  goto MAKEVENV
)
goto NOPYTHON

:MAKEVENV
echo Creating Python environment...
%PYBASE% -m venv .venv
if errorlevel 1 goto PYVENVFAIL
if not exist "%PYEXE%" goto PYVENVFAIL

:PYREADY
echo Python environment: %PYEXE%

rem ----------------------------------------------------------
rem Frontend dependencies and production build.
rem Always build so the current source changes are used.
rem ----------------------------------------------------------
echo.
echo [1/4] Installing/checking website packages...
rem Check the actual local CLI binaries, not just the node_modules folder.
rem A partial/copy of node_modules can exist without tsc/vite.
if not exist "node_modules\.bin\tsc.cmd" goto NPMINSTALL
if not exist "node_modules\.bin\vite.cmd" goto NPMINSTALL
echo Website packages already installed.
goto NPMREADY

:NPMINSTALL
echo Installing/reparing website packages (including dev dependencies)...
call npm install --include=dev
if errorlevel 1 goto NPMFAIL

:NPMREADY

echo.
echo [2/4] Building website...
call npm run build
if errorlevel 1 goto BUILDFAIL
if not exist "dist\index.html" goto BUILDFAIL

rem ----------------------------------------------------------
rem Backend dependencies. The marker is only an optimization;
rem the import test below repairs the environment if necessary.
rem ----------------------------------------------------------
echo.
echo [3/4] Checking Python packages...
if not exist ".venv\.requirements-installed" (
  call "%PYEXE%" -m pip install --upgrade pip
  if errorlevel 1 goto PIPFAIL
  call "%PYEXE%" -m pip install -r "server\requirements.txt"
  if errorlevel 1 goto PIPFAIL
  >".venv\.requirements-installed" echo installed
)

"%PYEXE%" -c "import fastapi, uvicorn; import server.main; print('Backend check OK')" >nul 2>&1
if errorlevel 1 (
  echo Repairing Python packages...
  del /q ".venv\.requirements-installed" >nul 2>&1
  call "%PYEXE%" -m pip install -r "server\requirements.txt"
  if errorlevel 1 goto PIPFAIL
  "%PYEXE%" -c "import fastapi, uvicorn; import server.main" >nul 2>&1
  if errorlevel 1 goto BACKENDFAIL
)

rem ----------------------------------------------------------
rem Start FastAPI. It serves the freshly built dist folder.
rem ----------------------------------------------------------
echo.
echo [4/4] Starting KisanMausam...
start "KisanMausam Server" /D "%~dp0" cmd /k ""%PYEXE%" -m uvicorn server.main:app --host 127.0.0.1 --port 8000"

echo Waiting for the server...
for /l %%i in (1,1,60) do (
  powershell -NoProfile -Command "try { $r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health -TimeoutSec 1; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>&1
  if not errorlevel 1 goto READY
  timeout /t 1 /nobreak >nul
)

echo.
echo ERROR: The server did not start within 60 seconds.
echo Keep this window open and check the "KisanMausam Server" window for the exact error.
pause
exit /b 1

:READY
echo.
echo ========================================================
echo KisanMausam is running successfully.
echo Open: http://127.0.0.1:8000
echo.
echo Keep the server window open while using the app.
echo Use STOP_KISANMAUSAM.bat when finished.
echo ========================================================
start "" "http://127.0.0.1:8000"
pause
exit /b 0

:NONODE
echo ERROR: Node.js is not installed or is not in PATH.
echo Install Node.js LTS, restart PowerShell, and run this again.
pause
exit /b 1

:NONPM
echo ERROR: npm is not available. Reinstall Node.js LTS and run this again.
pause
exit /b 1

:NOPYTHON
echo ERROR: Python 3.11+ is not installed or is not in PATH.
pause
exit /b 1

:NPMFAIL
echo ERROR: npm install failed. Check the message above and your internet connection.
pause
exit /b 1

:BUILDFAIL
echo ERROR: The frontend build failed. Check the message above.
pause
exit /b 1

:PYVENVFAIL
echo ERROR: Could not create the Python environment.
pause
exit /b 1

:PIPFAIL
echo ERROR: Python package installation failed. Check your internet connection and the message above.
pause
exit /b 1

:BACKENDFAIL
echo ERROR: The backend could not be imported after installing dependencies.
echo Check the "KisanMausam Server" output or run the command manually.
pause
exit /b 1
