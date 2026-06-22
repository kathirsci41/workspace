param(
    [string]$RunName = "validation-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackendRoot = Join-Path $ProjectRoot "backend"
$RunRoot = Join-Path $ProjectRoot "validation-runs\$RunName"
$DatabasePath = Join-Path $RunRoot "order_assurance.db"
$StoragePath = Join-Path $RunRoot "storage\documents"
$ArtifactsPath = Join-Path $RunRoot "artifacts"
$DownloadsPath = Join-Path $RunRoot "downloads"
$ActivationPath = Join-Path $RunRoot "activate.ps1"

if (Test-Path -LiteralPath $RunRoot) {
    throw "Validation run already exists: $RunRoot"
}

New-Item -ItemType Directory -Path $RunRoot | Out-Null
New-Item -ItemType Directory -Path $StoragePath -Force | Out-Null
New-Item -ItemType Directory -Path $ArtifactsPath | Out-Null
New-Item -ItemType Directory -Path $DownloadsPath | Out-Null

$DatabaseUrl = "sqlite:///" + ($DatabasePath -replace "\\", "/")
$activation = @"
`$env:DATABASE_URL="$DatabaseUrl"
`$env:STORAGE_DIR="$StoragePath"
`$env:APP_ENV="development"
`$env:ENABLE_DEV_TOOLS="false"
`$env:VITE_API_BASE_URL="http://127.0.0.1:8100/api"
"@
[System.IO.File]::WriteAllText($ActivationPath, $activation, [System.Text.UTF8Encoding]::new($false))

$previousDatabaseUrl = $env:DATABASE_URL
$previousStorageDir = $env:STORAGE_DIR
try {
    $env:DATABASE_URL = $DatabaseUrl
    $env:STORAGE_DIR = $StoragePath
    Push-Location $BackendRoot
    python -m app.migrations.runner up
    if ($LASTEXITCODE -ne 0) {
        throw "Migration command failed with exit code $LASTEXITCODE."
    }
    # Stamp alembic_version without re-running migrations (tables already created above).
    alembic stamp head
    if ($LASTEXITCODE -ne 0) {
        throw "Alembic stamp failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
    $env:DATABASE_URL = $previousDatabaseUrl
    $env:STORAGE_DIR = $previousStorageDir
}

Write-Host "Created clean validation runtime:" -ForegroundColor Green
Write-Host "  Run:       $RunName"
Write-Host "  Database:  $DatabasePath"
Write-Host "  Uploads:   $StoragePath"
Write-Host "  Artifacts: $ArtifactsPath"
Write-Host "  Downloads: $DownloadsPath"
Write-Host ""
Write-Host "Before starting, ensure ports 8100 and 5180 are free." -ForegroundColor Yellow
Write-Host "If the Docker stack is running, use: docker compose down"
Write-Host "Never add -v when preserving Build 1 data."
Write-Host ""
Write-Host "Backend terminal:"
Write-Host "  . `"$ActivationPath`""
Write-Host "  Set-Location `"$BackendRoot`""
Write-Host "  python -m uvicorn app.main:app --host 127.0.0.1 --port 8100"
Write-Host ""
Write-Host "Frontend terminal:"
Write-Host "  `$env:VITE_API_BASE_URL=`"http://127.0.0.1:8100/api`""
Write-Host "  Set-Location `"$ProjectRoot\frontend`""
Write-Host "  npm run dev"
