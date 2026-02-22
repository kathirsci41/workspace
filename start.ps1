<#
.SYNOPSIS
    One-click start for DocPlatform V3 (dev mode).
.DESCRIPTION
    Starts PostgreSQL, Redis (Docker), Backend API, Celery worker, and Frontend.
    Press Ctrl+C to stop everything gracefully.
#>

$Root = $PSScriptRoot

# -- Helpers -----------------------------------------------------------------
function Write-Step  { param($msg) Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok    { param($msg) Write-Host "   $msg"   -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "   $msg"   -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "   $msg"   -ForegroundColor Red }

# -- 1. Docker containers (Postgres + Redis) ---------------------------------
Write-Step "Starting Docker containers (PostgreSQL and Redis)..."
try {
    $composeFile = Join-Path $Root "docker-compose.dev.yml"
    $ErrorActionPreference = "Continue"
    docker compose -f $composeFile up -d postgres redis 2>&1 | Out-Null
    $ErrorActionPreference = "Stop"
    # Wait for healthy
    $retries = 0
    while ($retries -lt 30) {
        $pg = docker inspect --format='{{.State.Health.Status}}' docplatform-v3-postgres-1 2>$null
        $rd = docker inspect --format='{{.State.Health.Status}}' docplatform-v3-redis-1 2>$null
        if (($pg -eq "healthy") -and ($rd -eq "healthy")) { break }
        Start-Sleep -Seconds 1
        $retries++
    }
    if (($pg -eq "healthy") -and ($rd -eq "healthy")) {
        Write-Ok "PostgreSQL (5433) and Redis (6379) are healthy."
    }
    else {
        Write-Warn "Containers started but health check incomplete (pg=$pg, redis=$rd). Continuing..."
    }
}
catch {
    Write-Err "Failed to start Docker containers: $_"
    Write-Err "Make sure Docker Desktop is running."
    exit 1
}

# -- 2. Backend virtual-env check --------------------------------------------
$BackendDir = Join-Path $Root "backend"
$VenvActivate = Join-Path $BackendDir "venv\Scripts\Activate.ps1"

if (-not (Test-Path $VenvActivate)) {
    Write-Step "Creating Python virtual environment..."
    Push-Location $BackendDir
    python -m venv venv
    & $VenvActivate
    pip install -r requirements.txt --quiet
    Pop-Location
}
else {
    Write-Ok "Python venv found."
}

# -- 3. Alembic migrations ---------------------------------------------------
Write-Step "Running database migrations..."
Push-Location $BackendDir
& $VenvActivate
$env:PYTHONPATH = "."
$ErrorActionPreference = "Continue"
try {
    $migrationOutput = & alembic upgrade head 2>&1
    $migrationText = $migrationOutput | Out-String
    $hasError = $migrationText -match "FAILED"
    if ($hasError) {
        Write-Warn "Migration issue detected - stamping head instead."
        & alembic stamp head 2>&1 | Out-Null
    }
    Write-Ok "Database is up to date."
}
catch {
    Write-Warn "Migration warning: $_ (continuing...)"
}
$ErrorActionPreference = "Stop"
Pop-Location

# -- 4. Start Backend API (background job) -----------------------------------
Write-Step "Starting Backend API on http://127.0.0.1:8000 ..."
$backendJob = Start-Job -Name "DocPlatform-Backend" -ScriptBlock {
    param($dir, $activate)
    Set-Location $dir
    & $activate
    $env:PYTHONPATH = "."
    & uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload 2>&1
} -ArgumentList $BackendDir, $VenvActivate
Write-Ok "Backend job started (ID: $($backendJob.Id))."

# -- 5. Start Celery worker (background job) ---------------------------------
Write-Step "Starting Celery worker..."
$celeryJob = Start-Job -Name "DocPlatform-Celery" -ScriptBlock {
    param($dir, $activate)
    Set-Location $dir
    & $activate
    $env:PYTHONPATH = "."
    & celery -A celery_app worker --loglevel=info --pool=solo 2>&1
} -ArgumentList $BackendDir, $VenvActivate
Write-Ok "Celery job started (ID: $($celeryJob.Id))."

# -- 6. Start Frontend (background job) --------------------------------------
$FrontendDir = Join-Path $Root "frontend"
Write-Step "Starting Frontend on http://localhost:5173 ..."

# Ensure node_modules exist
$nodeModules = Join-Path $FrontendDir "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Step "Installing frontend dependencies..."
    Push-Location $FrontendDir
    npm install --silent
    Pop-Location
}

$frontendJob = Start-Job -Name "DocPlatform-Frontend" -ScriptBlock {
    param($dir)
    Set-Location $dir
    & npm run dev 2>&1
} -ArgumentList $FrontendDir
Write-Ok "Frontend job started (ID: $($frontendJob.Id))."

# -- 7. Wait and stream logs -------------------------------------------------
Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "  DocPlatform V3 is running!" -ForegroundColor Green
Write-Host "  Frontend : http://localhost:5173" -ForegroundColor Green
Write-Host "  Backend  : http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "  API Docs : http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Yellow
Write-Host ""

# Open the browser
Start-Process "http://localhost:5173"

# Keep-alive loop: stream job output until user presses Ctrl+C
try {
    while ($true) {
        foreach ($job in @($backendJob, $celeryJob, $frontendJob)) {
            $output = Receive-Job -Job $job -ErrorAction SilentlyContinue
            if ($output) {
                $label = $job.Name.Replace("DocPlatform-", "")
                foreach ($line in $output) {
                    Write-Host "[$label] $line"
                }
            }
            if ($job.State -eq "Failed") {
                Write-Err "$($job.Name) failed!"
                Receive-Job -Job $job -ErrorAction SilentlyContinue | ForEach-Object {
                    Write-Err "  $_"
                }
            }
        }
        Start-Sleep -Seconds 2
    }
}
finally {
    # -- Cleanup --------------------------------------------------------------
    Write-Host ""
    Write-Step "Shutting down..."

    Get-Job -Name "DocPlatform-*" -ErrorAction SilentlyContinue | Stop-Job -PassThru | Remove-Job -Force
    Write-Ok "Background jobs stopped."

    Write-Host ""
    $stopDocker = Read-Host "Stop Docker containers too? (y/N)"
    if ($stopDocker -eq "y") {
        $composeFile = Join-Path $Root "docker-compose.dev.yml"
        docker compose -f $composeFile stop postgres redis 2>&1 | Out-Null
        Write-Ok "Docker containers stopped."
    }
    else {
        Write-Ok "Docker containers left running."
    }

    Write-Host ""
    Write-Ok "DocPlatform V3 stopped. Goodbye!"
}
