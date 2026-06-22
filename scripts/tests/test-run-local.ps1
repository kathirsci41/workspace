#Requires -Version 5.1

$ErrorActionPreference = 'Stop'

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$RunLocalPath = Join-Path $ProjectRoot 'scripts\run-local.ps1'
$PackageJsonPath = Join-Path $ProjectRoot 'frontend\package.json'

$runLocal = Get-Content -Path $RunLocalPath -Raw
$packageJson = Get-Content -Path $PackageJsonPath -Raw | ConvertFrom-Json
$devScript = [string]$packageJson.scripts.dev

$failures = [System.Collections.Generic.List[string]]::new()

if ($devScript -match '(^|\s)--host\s+' -or $devScript -match '(^|\s)--port\s+') {
    if ($runLocal -notmatch '(?m)^\s*npm\s+run\s+dev\s+2>&1\s*$') {
        $failures.Add('frontend/package.json dev script already sets host/port, so run-local.ps1 must start the frontend with only: npm run dev')
    }

    if ($runLocal -match 'npm\s+run\s+dev\s+--\s+--host') {
        $failures.Add('run-local.ps1 forwards duplicate --host/--port arguments to npm run dev')
    }
}

if ($runLocal -notmatch '\$FrontendUrl\s*=\s*"http://127\.0\.0\.1:\$FrontendPort"') {
    $failures.Add('run-local.ps1 should probe the frontend URL when waiting for frontend readiness')
}

if ($runLocal -notmatch 'return\s+\(\$r\.StatusCode\s+-eq\s+200\)') {
    $failures.Add('Test-Http should treat HTTP 200 as ready')
}

$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $RunLocalPath,
    [ref]$tokens,
    [ref]$parseErrors
)

if ($parseErrors) {
    $failures.Add('run-local.ps1 should parse without PowerShell syntax errors')
} else {
    $launchIfs = $ast.FindAll(
        {
            param($node)
            $node -is [System.Management.Automation.Language.IfStatementAst] -and
                ($node.Clauses | Where-Object {
                    $_.Item1.Extent.Text -in @('$existingBackend', '$existingFrontend')
                })
        },
        $true
    )
    $backendIf = $launchIfs | Where-Object {
        ($_.Clauses | Select-Object -First 1).Item1.Extent.Text -eq '$existingBackend'
    } | Select-Object -First 1
    $frontendIf = $launchIfs | Where-Object {
        ($_.Clauses | Select-Object -First 1).Item1.Extent.Text -eq '$existingFrontend'
    } | Select-Object -First 1

    if (-not $backendIf -or -not $frontendIf -or $backendIf.Extent.EndLineNumber -ge $frontendIf.Extent.StartLineNumber) {
        $failures.Add('backend and frontend launch branches should parse as separate if statements')
    }
}

if ($failures.Count -gt 0) {
    throw ($failures -join [Environment]::NewLine)
}

Write-Host 'OK run-local.ps1 frontend startup command configuration'
