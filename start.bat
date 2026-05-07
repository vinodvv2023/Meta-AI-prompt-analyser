@echo off
setlocal
set "ROOT=%~dp0"
set "MEILI_EXE=meilisearch-enterprise-windows-amd64.exe"

echo.
echo  ====================================================
echo   Prompt Explorer ^| Meta AI
echo  ====================================================
echo.

REM ─── 1. Meilisearch ──────────────────────────────────────────────────────
echo [1/3] Starting Meilisearch...
if not exist "%ROOT%meilisearch\%MEILI_EXE%" (
    echo  ERROR: %MEILI_EXE% not found in meilisearch\
    echo  Please place the binary in: %ROOT%meilisearch\
    pause
    exit /b 1
)
if not exist "%ROOT%meili_data" mkdir "%ROOT%meili_data"
start "Meilisearch" cmd /k "cd /d "%ROOT%meilisearch" && %MEILI_EXE% --master-key masterKey123 --db-path "..\meili_data" --env development"

REM Wait for Meilisearch to be ready
echo  Waiting for Meilisearch to start...
timeout /t 8 /nobreak >nul

REM ─── 2. FastAPI Backend ───────────────────────────────────────────────────
echo [2/3] Starting FastAPI backend...
start "Backend" cmd /k "cd /d "%ROOT%backend" && "%ROOT%.venv\Scripts\python.exe" -m uvicorn main:app --reload --port 8000"

REM Wait for backend
timeout /t 3 /nobreak >nul

REM ─── 3. Vite Frontend ────────────────────────────────────────────────────
echo [3/3] Starting Vite frontend...
start "Frontend" cmd /k "cd /d "%ROOT%frontend" && npm.cmd run dev"

echo.
echo  ====================================================
echo   All services starting:
echo     Meilisearch  ^>  http://localhost:7700
echo     Backend API  ^>  http://localhost:8000/docs
echo     App UI       ^>  http://localhost:5173
echo  ====================================================
echo.
echo  (Close this window when you're done — or close the)
echo  (individual terminal windows to stop each service.) 
echo.
timeout /t 5 /nobreak >nul
start "" "http://localhost:5173"
