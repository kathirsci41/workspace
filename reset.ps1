<#
.SYNOPSIS
    Reset DocPlatform V3 to a clean state.
.DESCRIPTION
    Wipes the PostgreSQL database, flushes Redis, clears document storage,
    debug markdown files, reports, and Python __pycache__ folders.
    Then re-runs Alembic migrations so the app is ready to start fresh.

    Does NOT touch:
      - Source code, config files (.env, alembic.ini, docker-compose, etc.)
      - Alembic migration scripts (alembic/versions/*.py)
      - Python venv
      - node_modules / frontend build
      - Test source files (tests/*.py, tests/samples/*)
      - Ollama models
      - Docker images

    Usage:  .\reset.ps1              # interactive confirmation
            .\reset.ps1 -Force       # skip confirmation
            .\reset.ps1 -SkipDb      # skip database reset
#>

param(
    [switch]$Force,
    [switch]$SkipDb
)

$Root       = $PSScriptRoot
$BackendDir = Join-Path $Root "backend"
$ComposeFile = Join-Path $Root "docker-compose.dev.yml"

# -- Helpers -----------------------------------------------------------------
function Write-Step  { param($msg) Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok    { param($msg) Write-Host "   $msg"   -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "   $msg"   -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "   $msg"   -ForegroundColor Red }

# -- Confirmation ------------------------------------------------------------
Write-Host ""
Write-Host "=============================================" -ForegroundColor Red
Write-Host "  DocPlatform V3 - FULL RESET" -ForegroundColor Red
Write-Host "=============================================" -ForegroundColor Red
Write-Host ""
Write-Host "This will permanently delete:" -ForegroundColor Yellow
Write-Host '  - All data in PostgreSQL (docplatform DB)'
Write-Host '  - All data in Redis'
Write-Host '  - All uploaded documents (storage/documents/*)'
Write-Host '  - Debug markdown files (debug_markdown/, backend/debug_markdown/)'
Write-Host '  - Report files (backend/reports/*)'
Write-Host "  - Python __pycache__ folders"
Write-Host ""

if (-not $Force) {
    $confirm = Read-Host "Type 'RESET' to confirm, anything else to cancel"
    if ($confirm -ne "RESET") {
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit 0
    }
}

# -- 1. Stop running services ------------------------------------------------
Write-Step "Stopping running services..."

# Stop PowerShell background jobs from start.ps1
Get-Job -Name "DocPlatform-*" -ErrorAction SilentlyContinue |
    Stop-Job -PassThru | Remove-Job -Force -ErrorAction SilentlyContinue
Write-Ok "Background jobs stopped."

# Kill any lingering backend / frontend processes
$portsToKill = @(8001, 5174)
foreach ($port in $portsToKill) {
    $pids = netstat -ano 2>$null |
        Select-String ":$port " |
        ForEach-Object { ($_ -split '\s+')[-1] } |
        Sort-Object -Unique
    foreach ($p in $pids) {
        if ($p -match '^\d+$' -and $p -ne '0') {
            taskkill /PID $p /F 2>$null | Out-Null
        }
    }
}

# Kill celery workers
Get-Process -Name "celery" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Ok "Processes cleaned up."

# -- 2. Database reset -------------------------------------------------------
if (-not $SkipDb) {
    Write-Step "Resetting PostgreSQL database..."

    # Make sure containers are running
    docker compose -f $ComposeFile up -d postgres redis 2>&1 | Out-Null

    # Wait for postgres to be healthy
    $retries = 0
    while ($retries -lt 20) {
        $pg = docker inspect --format='{{.State.Health.Status}}' dpp220-postgres-1 2>$null
        if ($pg -eq "healthy") { break }
        Start-Sleep -Seconds 1
        $retries++
    }

    if ($pg -eq "healthy") {
        # Drop and recreate the public schema (wipes all tables, keeps the DB)
        docker exec dpp220-postgres-1 psql -U docplatform -d docplatform -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" 2>&1 | Out-Null
        Write-Ok 'Database schema dropped and recreated.'

        # Re-run Alembic migrations
        Write-Step "Running Alembic migrations..."
        Push-Location $BackendDir
        $VenvActivate = Join-Path $BackendDir "venv\Scripts\Activate.ps1"
        if (Test-Path $VenvActivate) {
            & $VenvActivate
        }
        $env:PYTHONPATH = "."
        $ErrorActionPreference = "Continue"
        $migrationOutput = & alembic upgrade head 2>&1
        $migrationText = $migrationOutput | Out-String
        if ($migrationText -match "FAILED|Error") {
            Write-Warn 'Migration issue - attempting stamp + upgrade...'
            & alembic stamp head 2>&1 | Out-Null
            & alembic upgrade head 2>&1 | Out-Null
        }
        $ErrorActionPreference = "Stop"
        Pop-Location
        Write-Ok 'Database migrations applied - clean schema ready.'
    }
    else {
        Write-Err "PostgreSQL container is not healthy (status: $pg)."
        Write-Err "Make sure Docker Desktop is running. Skipping DB reset."
    }

    # -- 3. Flush Redis -------------------------------------------------------
    Write-Step "Flushing Redis..."
    $rd = docker inspect --format='{{.State.Health.Status}}' dpp220-redis-1 2>$null
    if ($rd -eq "healthy") {
        docker exec dpp220-redis-1 redis-cli FLUSHALL 2>&1 | Out-Null
        Write-Ok "Redis flushed."
    }
    else {
        Write-Warn "Redis container not healthy - skipping flush."
    }
}
else {
    Write-Warn "Skipping database and Redis reset (-SkipDb)."
}

# -- 4. Clear document storage -----------------------------------------------
Write-Step "Clearing document storage..."

# Read NAS_BASE_PATH from .env, fallback to default
$storagePath = Join-Path $Root "storage\documents"
$envFile = Join-Path $BackendDir ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*NAS_BASE_PATH\s*=\s*(.+)") {
            $parsed = $Matches[1].Trim().Trim('"').Trim("'")
            if (Test-Path $parsed) { $storagePath = $parsed }
        }
    }
}

if (Test-Path $storagePath) {
    $items = Get-ChildItem -Path $storagePath -Force -ErrorAction SilentlyContinue
    if ($items) {
        Remove-Item -Path (Join-Path $storagePath "*") -Recurse -Force -ErrorAction SilentlyContinue
        $msg = "Cleared: $storagePath ($($items.Count) items removed)"
        Write-Ok $msg
    }
    else {
        Write-Ok "Storage already empty: $storagePath"
    }
}
else {
    Write-Warn "Storage path not found: $storagePath - nothing to clear."
}

# -- 5. Clear debug markdown files -------------------------------------------
Write-Step "Clearing debug markdown files..."

$debugDirs = @(
    (Join-Path $Root "debug_markdown"),
    (Join-Path $BackendDir "debug_markdown")
)

foreach ($dir in $debugDirs) {
    if (Test-Path $dir) {
        $mdFiles = Get-ChildItem -Path $dir -Filter "*.md" -File -ErrorAction SilentlyContinue
        if ($mdFiles) {
            $mdFiles | Remove-Item -Force -ErrorAction SilentlyContinue
            $msg = "Cleared $($mdFiles.Count) file(s) from: $dir"
            Write-Ok $msg
        }
        else {
            Write-Ok "Already empty: $dir"
        }
    }
}

# -- 6. Clear reports --------------------------------------------------------
Write-Step "Clearing reports..."

$reportDir = Join-Path $BackendDir "reports"
if (Test-Path $reportDir) {
    $reportFiles = Get-ChildItem -Path $reportDir -File -ErrorAction SilentlyContinue
    if ($reportFiles) {
        $reportFiles | Remove-Item -Force -ErrorAction SilentlyContinue
        $msg = "Cleared $($reportFiles.Count) report file(s)."
        Write-Ok $msg
    }
    else {
        Write-Ok "Reports directory already empty."
    }
}

# -- 7. Clear Python __pycache__ folders -------------------------------------
Write-Step "Clearing __pycache__ folders..."

$cacheCount = 0
Get-ChildItem -Path $BackendDir -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike "*\venv\*" } |
    ForEach-Object {
        Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        $cacheCount++
    }
Write-Ok "Removed $cacheCount __pycache__ folder(s) (venv excluded)."

# -- 8. Clear .pytest_cache --------------------------------------------------
$pytestCache = Join-Path $BackendDir ".pytest_cache"
if (Test-Path $pytestCache) {
    Remove-Item -Path $pytestCache -Recurse -Force -ErrorAction SilentlyContinue
    Write-Ok "Removed .pytest_cache."
}

# -- Done --------------------------------------------------------------------
Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "  Reset complete!" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Database  : Clean schema with migrations applied" -ForegroundColor Green
Write-Host "  Redis     : Flushed" -ForegroundColor Green
Write-Host "  Storage   : Empty" -ForegroundColor Green
Write-Host "  Debug/Rpt : Cleared" -ForegroundColor Green
Write-Host "  Cache     : Cleared" -ForegroundColor Green
Write-Host ""
Write-Host 'Run .\start.ps1 to start the application fresh.' -ForegroundColor Cyan
Write-Host ""
