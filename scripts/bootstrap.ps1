$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath ".venv")) {
    py -3.12 -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
}

Write-Output "Environment ready. Activate it with .\.venv\Scripts\Activate.ps1"
