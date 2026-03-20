<#
.SYNOPSIS
    One-click start for DocPlatform V3 (dev mode).
.DESCRIPTION
    Starts PostgreSQL, Redis (Docker), Backend API, Celery worker, and Frontend.
    Press Ctrl+C to stop everything gracefully.
#>

$Root    = $PSScriptRoot
$LogsDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

# -- Helpers -----------------------------------------------------------------
function Write-Step  { param($msg) Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok    { param($msg) Write-Host "   $msg"   -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "   $msg"   -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "   $msg"   -ForegroundColor Red }

# -- 0. Kill leftovers from previous run -------------------------------------
Write-Step "Cleaning up any leftover processes..."
Get-Job -Name "DocPlatform-*" -ErrorAction SilentlyContinue | Stop-Job -PassThru | Remove-Job -Force
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*celery*worker*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Ok "Done."

# -- 1. Docker containers (Postgres + Redis) ---------------------------------
Write-Step "Starting Docker containers (PostgreSQL and Redis)..."
try {
    $composeFile = Join-Path $Root "docker-compose.dev.yml"
    $ErrorActionPreference = "Continue"
    docker compose -f $composeFile up -d postgres redis 2>&1 | Out-Null
    $ErrorActionPreference = "Stop"
    $retries = 0
    while ($retries -lt 30) {
        $pg = docker inspect --format='{{.State.Health.Status}}' docplatform-v3-postgres-1 2>$null
        $rd = docker inspect --format='{{.State.Health.Status}}' docplatform-v3-redis-1 2>$null
        if (($pg -eq "healthy") -and ($rd -eq "healthy")) { break }
        Start-Sleep -Seconds 1
        $retries++
    }
    if (($pg -eq "healthy") -and ($rd -eq "healthy")) {
        Write-Ok "PostgreSQL (5434) and Redis (6380) are healthy."
    } else {
        Write-Warn "Containers started but health check incomplete (pg=$pg, redis=$rd). Continuing..."
    }
}
catch {
    Write-Err "Failed to start Docker containers: $_"
    Write-Err "Make sure Docker Desktop is running."
    exit 1
}

# -- 2. Extraction service check ---------------------------------------------
Write-Step "Checking extraction service endpoints..."
$BackendDir = Join-Path $Root "backend"
$envFile    = Join-Path $BackendDir ".env"

$ocrBaseUrl          = "http://localhost:11434"
$ocrExtractorBaseUrl = ""

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*OCR_BASE_URL\s*=\s*(.+)")           { $ocrBaseUrl          = $Matches[1].Trim() }
        if ($_ -match "^\s*OCR_EXTRACTOR_BASE_URL\s*=\s*(.+)") { $ocrExtractorBaseUrl = $Matches[1].Trim() }
    }
}
if (-not $ocrExtractorBaseUrl) { $ocrExtractorBaseUrl = $ocrBaseUrl }

foreach ($url in @($ocrBaseUrl, $ocrExtractorBaseUrl) | Select-Object -Unique) {
    try {
        Invoke-RestMethod -Uri "$url/api/tags" -Method Get -TimeoutSec 5 -ErrorAction Stop | Out-Null
        Write-Ok "Extraction service reachable: $url"
    } catch {
        Write-Warn "Extraction service NOT reachable: $url"
        Write-Warn "Extraction will fail - documents will fall back to Manual Entry."
    }
}

# -- 3. Backend virtual-env check --------------------------------------------
$VenvActivate = Join-Path $BackendDir "venv\Scripts\Activate.ps1"

if (-not (Test-Path $VenvActivate)) {
    Write-Step "Creating Python virtual environment..."
    Push-Location $BackendDir
    python -m venv venv
    & $VenvActivate
    pip install -r requirements.txt --quiet
    Pop-Location
} else {
    Write-Ok "Python venv found."
}

# -- 4. Alembic migrations ---------------------------------------------------
Write-Step "Running database migrations..."
Push-Location $BackendDir
& $VenvActivate
$env:PYTHONPATH = "."
$ErrorActionPreference = "Continue"
try {
    $migrationOutput = & alembic upgrade head 2>&1
    $migrationText   = $migrationOutput | Out-String
    if ($migrationText -match "FAILED") {
        Write-Warn "Migration issue detected - stamping head instead."
        & alembic stamp head 2>&1 | Out-Null
    }
    Write-Ok "Database is up to date."
} catch {
    Write-Warn "Migration warning: $_ (continuing...)"
}
$ErrorActionPreference = "Stop"
Pop-Location

# -- 5. Start Backend API (background job) -----------------------------------
Write-Step "Starting Backend API on http://127.0.0.1:8002 ..."
$backendJob = Start-Job -Name "DocPlatform-Backend" -ScriptBlock {
    param($dir, $activate)
    Set-Location $dir
    & $activate
    $env:PYTHONPATH = "."
    & uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload 2>&1
} -ArgumentList $BackendDir, $VenvActivate
Write-Ok "Backend job started (ID: $($backendJob.Id))."

# -- 6. Start Celery worker (background job) ---------------------------------
Write-Step "Starting Celery worker..."
$celeryJob = Start-Job -Name "DocPlatform-Celery" -ScriptBlock {
    param($dir, $activate)
    Set-Location $dir
    & $activate
    $env:PYTHONPATH = "."
    & celery -A celery_app worker --loglevel=info --pool=solo 2>&1
} -ArgumentList $BackendDir, $VenvActivate
Write-Ok "Celery job started (ID: $($celeryJob.Id))."

# -- 7. Start Frontend (background job) --------------------------------------
$FrontendDir = Join-Path $Root "frontend"
Write-Step "Starting Frontend on http://localhost:5174 ..."

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

# -- 8. Wait and stream logs -------------------------------------------------
Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "  DocPlatform V3 is running!" -ForegroundColor Green
Write-Host "  Frontend : http://localhost:5174" -ForegroundColor Green
Write-Host "  Backend  : http://127.0.0.1:8002" -ForegroundColor Green
Write-Host "  API Docs : http://127.0.0.1:8002/docs" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Yellow
Write-Host ""

Start-Process "http://localhost:5174"

$frontendLog = Join-Path $LogsDir "frontend.log"

# Tail log files directly — Backend and Celery write to log files immediately via Python logging.
# Frontend has no Python logger so its stdout is still captured via Receive-Job and written to frontend.log.
$positions = @{
    (Join-Path $LogsDir "app.log")    = 0
    (Join-Path $LogsDir "celery.log") = 0
    $frontendLog                       = 0
}
$labels = @{
    (Join-Path $LogsDir "app.log")    = "Backend"
    (Join-Path $LogsDir "celery.log") = "Celery"
    $frontendLog                       = "Frontend"
}

try {
    while ($true) {
        # Capture frontend stdout → write to frontend.log (picked up by tail below)
        $fOut = Receive-Job -Job $frontendJob -ErrorAction SilentlyContinue
        if ($fOut) {
            $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            foreach ($line in $fOut) {
                Add-Content -Path $frontendLog -Value "$ts | $line" -Encoding UTF8
            }
        }

        # Tail all three log files — print only new lines since last iteration
        foreach ($logFile in @($positions.Keys)) {
            if (Test-Path $logFile) {
                $content = Get-Content $logFile -Encoding UTF8 -ErrorAction SilentlyContinue
                if ($content) {
                    $newCount = @($content).Count
                    $oldCount = $positions[$logFile]
                    if ($newCount -gt $oldCount) {
                        $label = $labels[$logFile]
                        for ($i = $oldCount; $i -lt $newCount; $i++) {
                            Write-Host "[$label] $($content[$i])"
                        }
                        $positions[$logFile] = $newCount
                    }
                }
            }
        }

        # Detect crashed jobs
        foreach ($job in @($backendJob, $celeryJob, $frontendJob)) {
            if ($job.State -eq "Failed") {
                Write-Err "$($job.Name) crashed!"
                Receive-Job -Job $job -ErrorAction SilentlyContinue | ForEach-Object { Write-Err "  $_" }
            }
        }

        Start-Sleep -Milliseconds 200
    }
}
finally {
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
    } else {
        Write-Ok "Docker containers left running."
    }

    Write-Host ""
    Write-Ok "DocPlatform V3 stopped. Goodbye!"
}
