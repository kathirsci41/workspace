param(
    [int]$BackendPort = 8100,
    [int]$FrontendPort = 5180,
    [switch]$SkipMigrations,
    [switch]$InstallFrontendDeps,
    [switch]$OpenBrowser,
    [switch]$Detach
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$RuntimeDir = Join-Path $RepoRoot "runtime"
$LogDir = Join-Path $RuntimeDir "logs"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$StartedProcesses = New-Object System.Collections.Generic.List[System.Diagnostics.Process]

function Write-Step {
    param([string]$Message)
    Write-Host "[order-assurance] $Message"
}

function Test-HttpOk {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 3
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSeconds
        return [int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Get-PortOwner {
    param([int]$Port)

    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $connection) {
        return $null
    }

    $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
    if (-not $process) {
        return "PID $($connection.OwningProcess)"
    }
    return "$($process.ProcessName) PID $($process.Id)"
}

function Wait-ForHttp {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpOk -Url $Url) {
            Write-Step "$Name is ready: $Url"
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "$Name did not become ready within $TimeoutSeconds seconds: $Url"
}

function Start-LoggedProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [string]$StdOutPath,
        [string]$StdErrPath
    )

    Write-Step "Starting $Name"
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $StdOutPath `
        -RedirectStandardError $StdErrPath `
        -WindowStyle Hidden `
        -PassThru
    $StartedProcesses.Add($process) | Out-Null
    Write-Step "$Name PID $($process.Id)"
    return $process
}

function Stop-StartedProcesses {
    foreach ($process in $StartedProcesses) {
        try {
            if ($process -and -not $process.HasExited) {
                Write-Step "Stopping PID $($process.Id)"
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {
            Write-Warning "Could not stop PID $($process.Id): $($_.Exception.Message)"
        }
    }
}

try {
    Write-Step "Repository: $RepoRoot"

    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "python was not found on PATH. Install Python 3.11+ or activate the backend virtual environment."
    }
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm was not found on PATH. Install Node.js/npm before running the frontend."
    }

    if ($InstallFrontendDeps) {
        Write-Step "Installing frontend dependencies with npm ci"
        Push-Location $FrontendDir
        try {
            npm ci
        } finally {
            Pop-Location
        }
    } elseif (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
        throw "frontend/node_modules is missing. Run with -InstallFrontendDeps or run npm ci in frontend first."
    }

    $backendHealthUrl = "http://127.0.0.1:$BackendPort/api/health"
    $frontendUrl = "http://127.0.0.1:$FrontendPort/bundles"

    $backendAlreadyRunning = Test-HttpOk -Url $backendHealthUrl
    if ($backendAlreadyRunning) {
        Write-Step "Reusing existing backend: $backendHealthUrl"
    } else {
        $owner = Get-PortOwner -Port $BackendPort
        if ($owner) {
            throw "Backend port $BackendPort is already in use by $owner, but $backendHealthUrl is not healthy."
        }

        if (-not $SkipMigrations) {
            Write-Step "Running backend migrations"
            Push-Location $BackendDir
            try {
                python -m app.migrations.runner up
            } finally {
                Pop-Location
            }
        }

        $env:BACKEND_PORT = "$BackendPort"
        if (-not $env:APP_ENV) { $env:APP_ENV = "development" }
        if (-not $env:ENABLE_DEV_TOOLS) { $env:ENABLE_DEV_TOOLS = "true" }

        Start-LoggedProcess `
            -Name "backend" `
            -FilePath "python" `
            -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort") `
            -WorkingDirectory $BackendDir `
            -StdOutPath (Join-Path $LogDir "backend.stdout.log") `
            -StdErrPath (Join-Path $LogDir "backend.stderr.log") | Out-Null

        Wait-ForHttp -Name "Backend" -Url $backendHealthUrl
    }

    $frontendAlreadyRunning = Test-HttpOk -Url $frontendUrl
    if ($frontendAlreadyRunning) {
        Write-Step "Reusing existing frontend: $frontendUrl"
    } else {
        $owner = Get-PortOwner -Port $FrontendPort
        if ($owner) {
            throw "Frontend port $FrontendPort is already in use by $owner, but $frontendUrl is not responding."
        }

        $env:VITE_API_BASE_URL = "/api"
        $env:VITE_PROXY_API_TARGET = "http://127.0.0.1:$BackendPort"

        Start-LoggedProcess `
            -Name "frontend" `
            -FilePath "npm.cmd" `
            -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$FrontendPort") `
            -WorkingDirectory $FrontendDir `
            -StdOutPath (Join-Path $LogDir "frontend.stdout.log") `
            -StdErrPath (Join-Path $LogDir "frontend.stderr.log") | Out-Null

        Wait-ForHttp -Name "Frontend" -Url $frontendUrl
    }

    Write-Host ""
    Write-Step "Application is running without Docker"
    Write-Host "Frontend: $frontendUrl"
    Write-Host "Backend:  $backendHealthUrl"
    Write-Host "Logs:     $LogDir"
    Write-Host ""
    Write-Host "Press Ctrl+C to stop processes started by this script."

    if ($OpenBrowser) {
        Start-Process $frontendUrl
    }

    if ($Detach) {
        Write-Step "Detached mode: leaving started processes running."
        $StartedProcesses.Clear()
        return
    }

    while ($true) {
        foreach ($process in $StartedProcesses) {
            if ($process.HasExited) {
                throw "Started process PID $($process.Id) exited with code $($process.ExitCode). Check logs in $LogDir."
            }
        }
        Start-Sleep -Seconds 2
    }
} finally {
    Stop-StartedProcesses
}
