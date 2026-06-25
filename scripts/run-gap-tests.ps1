# Activate venv and run full test suite for gap fix verification
Set-Location "E:\PROJECTS\Experiments\Logistic\ODMP\order-assurance"
& ".venvs\backend-paddle311\Scripts\Activate.ps1"
Set-Location backend
python -m pytest tests -q 2>&1
