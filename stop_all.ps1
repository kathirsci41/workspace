Get-Job -Name 'DocPlatform-*' -ErrorAction SilentlyContinue | Stop-Job -PassThru | Remove-Job -Force
Write-Host 'PS jobs stopped.'

$pids8000 = netstat -ano | Select-String ':8000 ' | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
foreach ($p in $pids8000) { if ($p -match '^\d+$' -and $p -ne '0') { taskkill /PID $p /F 2>$null; Write-Host "Killed PID $p (port 8000)" } }

$pids5173 = netstat -ano | Select-String ':5173 ' | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
foreach ($p in $pids5173) { if ($p -match '^\d+$' -and $p -ne '0') { taskkill /PID $p /F 2>$null; Write-Host "Killed PID $p (port 5173)" } }

Get-Process -Name 'celery' -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host 'All clear.'
