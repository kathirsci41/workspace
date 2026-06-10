param(
    [Parameter(Mandatory = $true)]
    [string]$RunName,
    [int]$Port = 8100
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackendRoot = Join-Path $ProjectRoot "backend"
$ActivationPath = Join-Path $ProjectRoot "validation-runs\$RunName\activate.ps1"

if (-not (Test-Path -LiteralPath $ActivationPath)) {
    throw "Validation activation file not found: $ActivationPath"
}

. $ActivationPath
Set-Location $BackendRoot
python -m uvicorn app.main:app --host 127.0.0.1 --port $Port
