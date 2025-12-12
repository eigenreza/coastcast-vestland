$ErrorActionPreference = "Stop"
$api = Start-Process -FilePath ".\.venv\Scripts\uvicorn.exe" -ArgumentList "coastcast.api.main:app", "--host", "127.0.0.1", "--port", "8000" -PassThru -WindowStyle Hidden
try {
    & .\.venv\Scripts\streamlit.exe run src/coastcast/dashboard/app.py
}
finally {
    Stop-Process -Id $api.Id -ErrorAction SilentlyContinue
}
