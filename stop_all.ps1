Get-Job -Name 'DocPlatform-*' -ErrorAction SilentlyContinue | Stop-Job -PassThru | Remove-Job -Force
Write-Host 'PS jobs stopped.'

$pids8002 = netstat -ano | Select-String ':8002 ' | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
foreach ($p in $pids8002) { if ($p -match '^\d+$' -and $p -ne '0') { taskkill /PID $p /F 2>$null; Write-Host "Killed PID $p (port 8002)" } }

$pids5174 = netstat -ano | Select-String ':5174 ' | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique
foreach ($p in $pids5174) { if ($p -match '^\d+$' -and $p -ne '0') { taskkill /PID $p /F 2>$null; Write-Host "Killed PID $p (port 5174)" } }

Get-Process -Name 'celery' -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host 'All clear.'
