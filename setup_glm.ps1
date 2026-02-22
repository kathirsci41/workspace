# GLM-OCR Two-Layer Setup Script
# Run this once to prepare Ollama models for the two-layer pipeline

Write-Host "=== GLM-OCR Two-Layer Setup ===" -ForegroundColor Cyan

# 1. Check Ollama is running
Write-Host "[1/4] Checking GLM-OCR..." -ForegroundColor Yellow
$models = ollama list 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Ollama is not running. Start it with: ollama serve" -ForegroundColor Red
    exit 1
}

if ($models -match "glm-ocr") {
    Write-Host "      glm-ocr: OK" -ForegroundColor Green
} else {
    Write-Host "      Pulling glm-ocr..." -ForegroundColor Yellow
    ollama pull glm-ocr
}

# 2. Pull extraction model
Write-Host "[2/4] Pulling extraction model (qwen2.5:7b)..." -ForegroundColor Yellow
if ($models -match "qwen2.5:7b") {
    Write-Host "      qwen2.5:7b: OK" -ForegroundColor Green
} else {
    ollama pull qwen2.5:7b
    Write-Host "      qwen2.5:7b: OK" -ForegroundColor Green
}

# 3. Create custom GLM-OCR model with larger context
Write-Host "[3/4] Creating custom GLM-OCR model with larger context..." -ForegroundColor Yellow
$modelfilePath = Join-Path $PSScriptRoot "Modelfile.glm"
if (-not (Test-Path $modelfilePath)) {
    Write-Host "  ERROR: Modelfile.glm not found at $modelfilePath" -ForegroundColor Red
    exit 1
}
ollama create glm-ocr-custom -f $modelfilePath
Write-Host "      glm-ocr-custom: OK" -ForegroundColor Green

# 4. Verify
Write-Host "[4/4] Verifying models..." -ForegroundColor Yellow
ollama list | Select-String -Pattern "glm-ocr-custom|qwen2.5:7b"

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host "Set these in your backend .env file:" -ForegroundColor White
Write-Host "  OCR_TWO_LAYER_ENABLED=true" -ForegroundColor White
Write-Host "  OCR_CUSTOM_MODEL=glm-ocr-custom" -ForegroundColor White
Write-Host "  OCR_EXTRACTOR_MODEL=qwen2.5:7b" -ForegroundColor White
