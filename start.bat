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
echo [2/4] Starting FastAPI backend...
start "Backend" cmd /k "cd /d "%ROOT%backend" && "%ROOT%.venv\Scripts\python.exe" -m uvicorn main:app --reload --port 8001"

REM Wait for backend
timeout /t 3 /nobreak >nul

REM ─── 3. Threads API (MCP source) ─────────────────────────────────────────
echo [3/4] Starting Threads API...
start "Threads API" cmd /k "cd /d "%ROOT%backend" && set THREADS_DB_PATHS=C:\Users\xtrem\Downloads\python_proj\threads\docs\docs\prompts_backup\prompts.db^|C:\Users\xtrem\Downloads\python_proj\threads\data\prompts.db&& "%ROOT%.venv\Scripts\python.exe" -m uvicorn threads_service.api:app --port 8002"

REM Wait for Threads API
timeout /t 3 /nobreak >nul

REM ─── 4. Vite Frontend ────────────────────────────────────────────────────
echo [4/4] Starting Vite frontend...
start "Frontend" cmd /k "cd /d "%ROOT%frontend" && npm.cmd run dev"

echo.
echo  ====================================================
echo   All services starting:
echo     Meilisearch   ^>  http://localhost:7700
echo     Backend API   ^>  http://localhost:8001/docs
echo     Threads API   ^>  http://localhost:8002/docs
echo     App UI        ^>  http://localhost:5173
echo  ====================================================
echo.
echo  (Close this window when you're done — or close the )
echo  (individual terminal windows to stop each service.) 
echo.
timeout /t 5 /nobreak >nul
start "" "http://localhost:5173"
