$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.backend-venv\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Backend environment not found. Create .backend-venv and install requirements.txt first.'
}

$env:PYTHONIOENCODING = 'utf-8'
& $python -m uvicorn src.backend.main:app --host 127.0.0.1 --port 18080 --reload