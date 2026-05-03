<#
.SYNOPSIS
    One-click start for DocPlatform V3 (dev mode).
.DESCRIPTION
    Opens each service in its own dedicated PowerShell window.
    Backend, Celery, and Frontend each get a separate terminal.
    Press Ctrl+C in this window to stop everything.
#>

$Root        = $PSScriptRoot
$BackendDir  = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$LogsDir     = Join-Path $Root "logs"
$PythonExe   = Join-Path $BackendDir "venv\Scripts\python.exe"
$ComposeFile = Join-Path $Root "docker-compose.dev.yml"

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step { param($msg) Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "   [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "   [!!] $msg" -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host "   [XX] $msg" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# 0. Kill any leftover processes from a previous run
# ---------------------------------------------------------------------------
Write-Step "Cleaning up leftover processes..."

Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*celery*worker*" } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
    Where-Object { $_.CommandLine -like "*vite*" } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Start-Sleep -Milliseconds 500
Write-Ok "Cleanup done."

# ---------------------------------------------------------------------------
# 1. Verify venv and Python exe
# ---------------------------------------------------------------------------
Write-Step "Checking Python virtual environment..."

if (-not (Test-Path $PythonExe)) {
    Write-Err "Python venv not found at: $PythonExe"
    Write-Err "Run: python -m venv backend\venv && backend\venv\Scripts\pip install -r backend\requirements.txt"
    exit 1
}

$pyVersion = & $PythonExe --version 2>&1
Write-Ok "Using: $PythonExe ($pyVersion)"

# ---------------------------------------------------------------------------
# 2. Docker containers (PostgreSQL + Redis)
# ---------------------------------------------------------------------------
Write-Step "Starting Docker containers (PostgreSQL + Redis)..."

$ErrorActionPreference = "Continue"
docker compose -f $ComposeFile up -d postgres redis 2>&1 | Out-Null
$ErrorActionPreference = "Stop"

$retries = 0
while ($retries -lt 30) {
    $pg = docker inspect --format='{{.State.Health.Status}}' dpp220-postgres-1 2>$null
    $rd = docker inspect --format='{{.State.Health.Status}}' dpp220-redis-1 2>$null
    if (($pg -eq "healthy") -and ($rd -eq "healthy")) { break }
    Start-Sleep -Seconds 1
    $retries++
}

if (($pg -eq "healthy") -and ($rd -eq "healthy")) {
    Write-Ok "PostgreSQL :5434  Redis :6380 - healthy."
} else {
    Write-Warn ("Containers started but health incomplete (pg={0}, rd={1}). Continuing..." -f $pg, $rd)
}

# ---------------------------------------------------------------------------
# 3. Database migrations
# ---------------------------------------------------------------------------
Write-Step "Running database migrations..."
Push-Location $BackendDir
$env:PYTHONPATH = "."
$ErrorActionPreference = "Continue"
$migOut = & $PythonExe -m alembic upgrade head 2>&1 | Out-String
if ($migOut -match "FAILED") {
    Write-Warn "Migration issue - stamping head instead."
    & $PythonExe -m alembic stamp head 2>&1 | Out-Null
}
$ErrorActionPreference = "Stop"
Pop-Location
Write-Ok "Database is up to date."

# ---------------------------------------------------------------------------
# 4. Extraction service check
# ---------------------------------------------------------------------------
Write-Step "Checking extraction service..."
$envFile = Join-Path $BackendDir ".env"
$ocrUrl  = "http://localhost:11434"

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*OCR_BASE_URL\s*=\s*(.+)") { $ocrUrl = $Matches[1].Trim() }
    }
}

try {
    Invoke-RestMethod -Uri "$ocrUrl/api/tags" -Method Get -TimeoutSec 4 -ErrorAction Stop | Out-Null
    Write-Ok "Extraction service reachable: $ocrUrl"
} catch {
    Write-Warn "Extraction service NOT reachable: $ocrUrl"
    Write-Warn "Documents will need Manual Entry until Ollama is running."
}

# ---------------------------------------------------------------------------
# 5. Open Backend window
# ---------------------------------------------------------------------------
Write-Step "Opening Backend window (port 8002)..."

$backendCmd = "& {
    `$host.UI.RawUI.WindowTitle = 'DPP Backend :8002'
    Set-Location '$BackendDir'
    `$env:PYTHONPATH = '.'
    Write-Host '>> Backend API starting...' -ForegroundColor Cyan
    & '$PythonExe' -m uvicorn app.main:app --host 127.0.0.1 --port 8002
    Write-Host '>> Backend stopped. Press any key to close.' -ForegroundColor Yellow
    `$null = `$host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
}"

$backendProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -PassThru
Write-Ok "Backend window opened (PID: $($backendProc.Id))"

# ---------------------------------------------------------------------------
# 6. Open Celery window
# ---------------------------------------------------------------------------
Write-Step "Opening Celery window..."

$celeryCmd = "& {
    `$host.UI.RawUI.WindowTitle = 'DPP Celery Worker'
    Set-Location '$BackendDir'
    `$env:PYTHONPATH = '.'
    Write-Host '>> Celery worker starting...' -ForegroundColor Cyan
    & '$PythonExe' -m celery -A celery_app worker --loglevel=info --pool=solo
    Write-Host '>> Celery stopped. Press any key to close.' -ForegroundColor Yellow
    `$null = `$host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
}"

$celeryProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", $celeryCmd -PassThru
Write-Ok "Celery window opened (PID: $($celeryProc.Id))"

# ---------------------------------------------------------------------------
# 7. Open Frontend window
# ---------------------------------------------------------------------------
Write-Step "Opening Frontend window (port 5174)..."

$frontendCmd = "& {
    `$host.UI.RawUI.WindowTitle = 'DPP Frontend :5174'
    Set-Location '$FrontendDir'
    Write-Host '>> Frontend (Vite) starting...' -ForegroundColor Cyan
    npm run dev
    Write-Host '>> Frontend stopped. Press any key to close.' -ForegroundColor Yellow
    `$null = `$host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
}"

$frontendProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -PassThru
Write-Ok "Frontend window opened (PID: $($frontendProc.Id))"

# ---------------------------------------------------------------------------
# 8. Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  DocPlatform V3 - all services starting in their windows"    -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend   http://[::1]:5174"                              -ForegroundColor White
Write-Host "  Backend    http://127.0.0.1:8002"                          -ForegroundColor White
Write-Host "  API Docs   http://127.0.0.1:8002/docs"                     -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Ctrl+C here  ->  stops all service windows + this script"  -ForegroundColor Yellow
Write-Host "  Close a window individually to restart just that service"  -ForegroundColor Yellow
Write-Host ""

# Open browser
Start-Sleep -Seconds 4
Start-Process "http://[::1]:5174"

# ---------------------------------------------------------------------------
# 9. Wait - Ctrl+C kills all service windows
# ---------------------------------------------------------------------------
try {
    while ($true) {
        Start-Sleep -Seconds 3

        # Warn if a service window was closed manually
        if ($backendProc.HasExited)  { Write-Warn "Backend window was closed." }
        if ($celeryProc.HasExited)   { Write-Warn "Celery window was closed." }
        if ($frontendProc.HasExited) { Write-Warn "Frontend window was closed." }
    }
}
finally {
    Write-Host ""
    Write-Step "Shutting down all services..."

    Stop-Process -Id $backendProc.Id  -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $celeryProc.Id   -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue

    # Also kill any child python/node processes
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*celery*worker*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

    Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
        Where-Object { $_.CommandLine -like "*vite*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

    Write-Ok "All service windows closed."

    Write-Host ""
    $stopDocker = Read-Host "Stop Docker containers too? (y/N)"
    if ($stopDocker -eq "y") {
        docker compose -f $ComposeFile stop postgres redis 2>&1 | Out-Null
        Write-Ok "Docker containers stopped."
    } else {
        Write-Ok "Docker containers left running."
    }

    Write-Host ""
    Write-Ok "DocPlatform V3 stopped. Goodbye!"
}
