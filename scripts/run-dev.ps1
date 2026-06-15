# Burtler 로컬 개발 서버 실행 스크립트
# 사용: powershell -ExecutionPolicy Bypass -File .\scripts\run-dev.ps1

param(
    [int]$Port = 8000
)

$AppDir = Split-Path $PSScriptRoot

# 1. 포트 점유 확인 및 종료
Write-Host "[run-dev] 포트 $Port 점유 확인 중..."
$listeners = netstat -ano 2>$null | Select-String ":$Port\s"

if ($listeners) {
    $pids = $listeners | ForEach-Object {
        if ($_ -match '\s+(\d+)\s*$') { [int]$Matches[1] }
    } | Sort-Object -Unique | Where-Object { $_ -gt 0 }

    foreach ($p in $pids) {
        try {
            Stop-Process -Id $p -Force -ErrorAction Stop
            Write-Host "[run-dev] PID $p 종료 완료."
        } catch {
            Write-Host "[run-dev] PID $p 이미 종료됨."
        }
    }
} else {
    Write-Host "[run-dev] 포트 $Port 비어있음."
}

# 2. uvicorn 백그라운드 실행
Write-Host "[run-dev] uvicorn 실행 중 (포트 $Port, --reload)..."
$Python = (Get-Command python -ErrorAction Stop).Source
$proc = Start-Process -FilePath $Python `
    -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port $Port --reload" `
    -WorkingDirectory $AppDir `
    -WindowStyle Hidden `
    -PassThru

Write-Host "[run-dev] PID $($proc.Id) 로 서버 시작됨."

# 3. 헬스체크 (최대 3회, 3초 간격)
$maxRetries = 3
$success = $false

for ($i = 1; $i -le $maxRetries; $i++) {
    Start-Sleep -Seconds 3
    $statusCode = curl.exe -s -o NUL -w "%{http_code}" --max-time 5 "http://localhost:$Port/health" 2>$null
    if ($statusCode -eq "200") {
        $success = $true
        break
    }
    Write-Host "[run-dev] 헬스체크 $i/$maxRetries 실패 (응답: $statusCode). 재시도 중..."
}

# 4. 결과 보고
if ($success) {
    Write-Host ""
    Write-Host "[run-dev] 서버 실행 중"
    Write-Host "[run-dev] 접속 URL: http://localhost:$Port"
} else {
    Write-Host "[run-dev] 서버 시작 실패. PID $($proc.Id) 로그를 확인하세요."
    exit 1
}
