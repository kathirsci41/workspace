param(
    [ValidateSet("up", "down", "restart", "reset", "status", "logs", "seed", "migrate", "health")]
    [string]$Action = "up",

    [switch]$Build,
    [switch]$Seed,
    [switch]$Volumes
)

$ErrorActionPreference = "Stop"

function Write-Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok($Message) {
    Write-Host "OK: $Message" -ForegroundColor Green
}

function Write-Warn($Message) {
    Write-Host "WARN: $Message" -ForegroundColor Yellow
}

function Run($Command, $Arguments) {
    Write-Host "`n$Command $Arguments" -ForegroundColor DarkGray
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Command $Arguments"
    }
}

function Find-ComposeFile {
    $current = Get-Location

    if (Test-Path "$current\docker-compose.yml") {
        return "$current\docker-compose.yml"
    }

    if (Test-Path "$current\order-assurance\docker-compose.yml") {
        return "$current\order-assurance\docker-compose.yml"
    }

    if ($PSScriptRoot -and (Test-Path "$PSScriptRoot\docker-compose.yml")) {
        return "$PSScriptRoot\docker-compose.yml"
    }

    throw "Could not find docker-compose.yml. Run this from project root or order-assurance folder."
}

function ComposeArgs($ExtraArgs) {
    $args = @("compose", "-f", $ComposeFile)
    if ($UseDevCompose -and $DevComposeFile) {
        $args += @("-f", $DevComposeFile)
    }
    return $args + $ExtraArgs
}

function Wait-BackendHealth {
    param(
        [int]$Attempts = 30,
        [int]$DelaySeconds = 2
    )

    Write-Step "Waiting for backend health"

    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            $response = & curl.exe -s http://127.0.0.1:8100/api/health
            if ($response -match '"status"\s*:\s*"ok"') {
                Write-Ok "Backend health OK"
                return
            }
        } catch {
            # retry
        }

        Write-Host "Waiting... attempt $i/$Attempts"
        Start-Sleep -Seconds $DelaySeconds
    }

    throw "Backend health check failed after $Attempts attempts."
}

function Run-Migrations {
    Write-Step "Running migrations"
    Run "docker" (ComposeArgs @("exec", "-T", "backend", "python", "-m", "app.migrations.runner", "up"))
}

function Seed-Panimalar {
    Write-Step "Seeding Panimalar demo bundle"
    Run "docker" (ComposeArgs @("exec", "-T", "backend", "python", "-m", "app.scripts.seed_panimalar_demo"))
}

$ComposeFile = Find-ComposeFile
$DevComposeFile = Join-Path (Split-Path $ComposeFile -Parent) "docker-compose.dev.yml"
if (-not (Test-Path $DevComposeFile)) {
    $DevComposeFile = $null
}
$UseDevCompose = $Seed -or $Action -in @("seed", "reset")
Write-Host "Using compose file: $ComposeFile" -ForegroundColor DarkGray
if ($UseDevCompose -and $DevComposeFile) {
    Write-Host "Using dev compose override: $DevComposeFile" -ForegroundColor DarkGray
}

switch ($Action) {
    "up" {
        Write-Step "Starting Order Assurance"

        if ($Build) {
            Run "docker" (ComposeArgs @("up", "--build", "-d"))
        } else {
            Run "docker" (ComposeArgs @("up", "-d"))
        }

        Run "docker" (ComposeArgs @("ps"))
        Wait-BackendHealth
        Run-Migrations

        if ($Seed) {
            Seed-Panimalar
        }

        Write-Ok "Order Assurance is running"
        Write-Host ""
        Write-Host "Frontend: http://127.0.0.1:5180" -ForegroundColor Green
        Write-Host "Backend:  http://127.0.0.1:8100/api/health" -ForegroundColor Green
    }

    "down" {
        Write-Step "Stopping Order Assurance"

        if ($Volumes) {
            Write-Warn "Removing containers and volumes"
            Run "docker" (ComposeArgs @("down", "-v"))
        } else {
            Run "docker" (ComposeArgs @("down"))
        }

        Write-Ok "Order Assurance stopped"
    }

    "restart" {
        Write-Step "Restarting Order Assurance"
        Run "docker" (ComposeArgs @("down"))

        if ($Build) {
            Run "docker" (ComposeArgs @("up", "--build", "-d"))
        } else {
            Run "docker" (ComposeArgs @("up", "-d"))
        }

        Run "docker" (ComposeArgs @("ps"))
        Wait-BackendHealth
        Run-Migrations

        if ($Seed) {
            Seed-Panimalar
        }

        Write-Ok "Order Assurance restarted"
    }

    "reset" {
        Write-Step "Resetting Order Assurance"
        Write-Warn "This removes database/storage volumes"
        Run "docker" (ComposeArgs @("down", "-v"))

        if ($Build) {
            Run "docker" (ComposeArgs @("up", "--build", "-d"))
        } else {
            Run "docker" (ComposeArgs @("up", "-d"))
        }

        Run "docker" (ComposeArgs @("ps"))
        Wait-BackendHealth
        Run-Migrations
        Seed-Panimalar

        Write-Ok "Order Assurance reset complete"
        Write-Host ""
        Write-Host "Frontend: http://127.0.0.1:5180" -ForegroundColor Green
    }

    "status" {
        Write-Step "Order Assurance status"
        Run "docker" (ComposeArgs @("ps"))
    }

    "logs" {
        Write-Step "Following backend logs"
        & docker @(ComposeArgs @("logs", "backend", "-f"))
    }

    "seed" {
        Wait-BackendHealth
        Seed-Panimalar
    }

    "migrate" {
        Wait-BackendHealth
        Run-Migrations
    }

    "health" {
        Wait-BackendHealth
        & curl.exe http://127.0.0.1:8100/api/health
    }
}
