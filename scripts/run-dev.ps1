# Burtler local dev server
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\run-dev.ps1

param(
    [int]$Port = 8000
)

$AppDir = Split-Path $PSScriptRoot

# 1. Kill any process occupying the port
Write-Host "[run-dev] Checking port $Port..."
$listeners = netstat -ano 2>$null | Select-String ":$Port\s"

if ($listeners) {
    $pids = $listeners | ForEach-Object {
        if ($_ -match '\s+(\d+)\s*$') { [int]$Matches[1] }
    } | Sort-Object -Unique | Where-Object { $_ -gt 0 }

    foreach ($p in $pids) {
        try {
            Stop-Process -Id $p -Force -ErrorAction Stop
            Write-Host "[run-dev] Killed PID $p."
        } catch {
            Write-Host "[run-dev] PID $p already gone."
        }
    }
} else {
    Write-Host "[run-dev] Port $Port is free."
}

# 2. Start uvicorn in background
Write-Host "[run-dev] Starting uvicorn on port $Port (--reload)..."
$Python = (Get-Command python -ErrorAction Stop).Source
$proc = Start-Process -FilePath $Python `
    -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port $Port --reload" `
    -WorkingDirectory $AppDir `
    -WindowStyle Hidden `
    -PassThru

Write-Host "[run-dev] Server started (PID $($proc.Id))."

# 3. Health check (up to 3 attempts, 3s apart)
$maxRetries = 3
$success = $false

for ($i = 1; $i -le $maxRetries; $i++) {
    Start-Sleep -Seconds 3
    $statusCode = curl.exe -s -o NUL -w "%{http_code}" --max-time 5 "http://localhost:$Port/health" 2>$null
    if ($statusCode -eq "200") {
        $success = $true
        break
    }
    Write-Host "[run-dev] Health check $i/$maxRetries failed (got: $statusCode). Retrying..."
}

# 4. Report
if ($success) {
    Write-Host ""
    Write-Host "[run-dev] Server is running."
    Write-Host "[run-dev] URL: http://localhost:$Port"
} else {
    Write-Host "[run-dev] Server failed to start. Check logs for PID $($proc.Id)."
    exit 1
}
