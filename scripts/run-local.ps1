#Requires -Version 5.1
<#
.SYNOPSIS
    Start Order Assurance (backend + frontend) locally with live terminal logs.

.DESCRIPTION
    Runs migrations, then launches the FastAPI backend (port 8100) and Vite
    frontend (port 5180) as background jobs whose output is streamed to this
    terminal in real time with colour-coded prefixes.

    Press Ctrl+C at any time to stop both services.

.PARAMETER BackendPort
    Port for the FastAPI backend. Default: 8100

.PARAMETER FrontendPort
    Port for the Vite dev server. Default: 5180

.PARAMETER SkipMigrations
    Skip the database migration step.

.PARAMETER OpenBrowser
    Open the app in the default browser once ready.

.EXAMPLE
    .\scripts\run-local.ps1
    .\scripts\run-local.ps1 -OpenBrowser
    .\scripts\run-local.ps1 -SkipMigrations
#>
param(
    [int]   $BackendPort      = 8100,
    [int]   $FrontendPort     = 5180,
    [switch]$SkipMigrations,
    [switch]$OpenBrowser
)

$ErrorActionPreference = 'Stop'

# Paths
$RepoRoot   = Resolve-Path (Join-Path $PSScriptRoot '..')
$BackendDir = Join-Path $RepoRoot 'backend'
$FrontendDir= Join-Path $RepoRoot 'frontend'

$BackendUrl = "http://127.0.0.1:$BackendPort/api/health"
$FrontendUrl= "http://127.0.0.1:$FrontendPort"
$AppUrl     = "http://127.0.0.1:$FrontendPort/bundles"

# Helpers
function Write-Banner {
    Write-Host ''
    Write-Host '  Order Assurance - Local Dev Server' -ForegroundColor White
    Write-Host "  Backend  : $BackendUrl"             -ForegroundColor DarkGray
    Write-Host "  Frontend : $AppUrl"                 -ForegroundColor DarkGray
    Write-Host '  Press Ctrl+C to stop.'              -ForegroundColor DarkGray
    Write-Host ''
}

function Write-Step([string]$Msg) {
    Write-Host "==> $Msg" -ForegroundColor Cyan
}

function Write-Ok([string]$Msg) {
    Write-Host "OK  $Msg" -ForegroundColor Green
}

function Write-Fail([string]$Msg) {
    Write-Host "ERR $Msg" -ForegroundColor Red
}

function Test-Port([int]$Port) {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    if ($conn) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        return if ($proc) { "$($proc.ProcessName) (PID $($proc.Id))" } else { "PID $($conn.OwningProcess)" }
    }
    return $null
}

function Test-Http([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Wait-Http([string]$Name, [string]$Url, [int]$Timeout = 60) {
    Write-Step "Waiting for $Name to be ready..."
    $deadline = (Get-Date).AddSeconds($Timeout)
    while ((Get-Date) -lt $deadline) {
        if (Test-Http $Url) { Write-Ok "$Name is ready"; return }
        Start-Sleep -Seconds 1
    }
    throw "$Name did not start within ${Timeout}s. Check logs above."
}

function Stop-Jobs([System.Collections.Generic.List[object]]$Jobs) {
    foreach ($j in $Jobs) {
        if ($j -and $j.State -ne 'Completed') {
            Stop-Job  $j -ErrorAction SilentlyContinue
            Remove-Job $j -Force -ErrorAction SilentlyContinue
        }
    }
}

function Drain-Job([object]$Job, [string]$Prefix, [ConsoleColor]$Color) {
    $lines = Receive-Job $Job -ErrorAction SilentlyContinue
    foreach ($line in $lines) {
        if ($null -ne $line) {
            Write-Host "$Prefix $line" -ForegroundColor $Color
        }
    }
}

# Pre-flight checks
Write-Banner

# Optional interpreter override (e.g. a PaddleOCR venv). Defaults to 'python'
# on PATH so existing behavior is unchanged when BACKEND_PYTHON is not set.
$BackendPython = if ($env:BACKEND_PYTHON) { $env:BACKEND_PYTHON } else { 'python' }
if ($env:BACKEND_PYTHON) {
    if (-not (Test-Path $env:BACKEND_PYTHON)) {
        Write-Fail "BACKEND_PYTHON is set but not found: $env:BACKEND_PYTHON"
        exit 1
    }
    Write-Step "Using BACKEND_PYTHON: $env:BACKEND_PYTHON"
} elseif (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Fail 'python not found on PATH. Install Python 3.11+ or activate your virtual environment.'
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Fail 'npm not found on PATH. Install Node.js before starting the frontend.'
    exit 1
}
if (-not (Test-Path (Join-Path $FrontendDir 'node_modules'))) {
    Write-Step 'node_modules missing - running npm ci...'
    Push-Location $FrontendDir
    npm ci
    Pop-Location
}

# Check ports
$existingBackend  = Test-Http $BackendUrl
$existingFrontend = Test-Http $FrontendUrl

if (-not $existingBackend) {
    $owner = Test-Port $BackendPort
    if ($owner) {
        Write-Fail "Port $BackendPort already used by $owner but backend health check failed."
        exit 1
    }
}
if (-not $existingFrontend) {
    $owner = Test-Port $FrontendPort
    if ($owner) {
        Write-Fail "Port $FrontendPort already used by $owner but frontend is not responding."
        exit 1
    }
}

# Migrations
if (-not $SkipMigrations -and -not $existingBackend) {
    Write-Step 'Running database migrations...'
    Push-Location $BackendDir
    & $BackendPython -m app.migrations.runner up
    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        Write-Fail 'Migrations failed.'
        exit 1
    }
    Pop-Location
    Write-Ok 'Migrations complete'
}

# Launch jobs
$jobs = [System.Collections.Generic.List[object]]::new()
$backendJob = $null
$frontendJob = $null

if ($existingBackend) {
    Write-Step "Backend already running - reusing :$BackendPort"
}
if (-not $existingBackend) {
    Write-Step "Starting backend on :$BackendPort ..."
    $backendJob = Start-Job -Name 'backend' -ScriptBlock {
        param($Dir, $Port, $Python)
        Set-Location $Dir
        $env:APP_ENV           = if ($env:APP_ENV)           { $env:APP_ENV }           else { 'development' }
        $env:ENABLE_DEV_TOOLS  = if ($env:ENABLE_DEV_TOOLS)  { $env:ENABLE_DEV_TOOLS }  else { 'true' }
        $env:BACKEND_PORT      = "$Port"
        & $Python -m uvicorn app.main:app `
            --host 127.0.0.1 `
            --port $Port `
            --reload `
            2>&1
    } -ArgumentList $BackendDir, $BackendPort, $BackendPython
    $jobs.Add($backendJob) | Out-Null
}

if ($existingFrontend) {
    Write-Step "Frontend already running - reusing :$FrontendPort"
}
if (-not $existingFrontend) {
    Write-Step "Starting frontend on :$FrontendPort ..."
    $frontendJob = Start-Job -Name 'frontend' -ScriptBlock {
        param($Dir, $ApiPort)
        Set-Location $Dir
        $env:VITE_API_BASE_URL      = '/api'
        $env:VITE_PROXY_API_TARGET  = "http://127.0.0.1:$ApiPort"
        npm run dev 2>&1
    } -ArgumentList $FrontendDir, $BackendPort
    $jobs.Add($frontendJob) | Out-Null
}

# Wait for ready
try {
    if ($backendJob) {
        # Stream early backend output while waiting
        $deadline = (Get-Date).AddSeconds(60)
        while ((Get-Date) -lt $deadline) {
            if ($backendJob) { Drain-Job $backendJob '[BACKEND ]' Cyan }
            if (Test-Http $BackendUrl) { Write-Ok "Backend ready at $BackendUrl"; break }
            Start-Sleep -Milliseconds 500
        }
        if (-not (Test-Http $BackendUrl)) {
            throw "Backend did not become ready within 60s."
        }
    }

    if ($frontendJob) {
        $deadline = (Get-Date).AddSeconds(60)
        while ((Get-Date) -lt $deadline) {
            if ($backendJob)  { Drain-Job $backendJob  '[BACKEND ]' Cyan  }
            if ($frontendJob) { Drain-Job $frontendJob '[FRONTEND]' Green }
            if (Test-Http $FrontendUrl) { Write-Ok "Frontend ready at $AppUrl"; break }
            Start-Sleep -Milliseconds 500
        }
        if (-not (Test-Http $FrontendUrl)) {
            throw "Frontend did not become ready within 60s."
        }
    }
} catch {
    Write-Fail $_
    Stop-Jobs $jobs
    exit 1
}

# Ready banner
Write-Host ''
Write-Host '  Application is running.' -ForegroundColor White
Write-Host "  Open : $AppUrl"          -ForegroundColor Green
Write-Host "  API  : $BackendUrl"      -ForegroundColor Green
Write-Host '  Ctrl+C to stop.'         -ForegroundColor DarkGray
Write-Host ''

if ($OpenBrowser) { Start-Process $AppUrl }

# Live log loop
try {
    while ($true) {
        if ($backendJob) {
            if ($backendJob.State -eq 'Failed') {
                Write-Fail 'Backend process exited unexpectedly.'
                Drain-Job $backendJob '[BACKEND ]' Red
                break
            }
            Drain-Job $backendJob '[BACKEND ]' Cyan
        }
        if ($frontendJob) {
            if ($frontendJob.State -eq 'Failed') {
                Write-Fail 'Frontend process exited unexpectedly.'
                Drain-Job $frontendJob '[FRONTEND]' Red
                break
            }
            Drain-Job $frontendJob '[FRONTEND]' Green
        }
        Start-Sleep -Milliseconds 300
    }
} finally {
    Write-Host ''
    Write-Step 'Stopping services...'
    Stop-Jobs $jobs
    Write-Ok 'Stopped.'
}
