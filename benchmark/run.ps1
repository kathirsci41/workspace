# LiteParse Benchmark Server
# Run from: order-assurance/benchmark/
# Open:     http://localhost:8001

Write-Host "Installing benchmark deps..." -ForegroundColor Cyan
pip install liteparse fastapi uvicorn python-multipart PyMuPDF --quiet

Write-Host ""
Write-Host "Starting benchmark server on http://localhost:8001" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""

$env:DATABASE_URL = "sqlite:///./benchmark_temp.db"
$env:APP_ENV = "benchmark"

python server.py
