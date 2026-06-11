# Burtler 배포 스크립트
# prd 브랜치 push 시 GitHub Actions(자체 호스팅 Windows x64)에서 자동 실행
# 수동 실행: powershell -ExecutionPolicy Bypass -File .\scripts\deploy.ps1

param(
    [int]$HttpsPort = 8443,
    [int]$HttpPort  = 8000
)

$AppName   = "Burtler"
$AppDir    = Split-Path $PSScriptRoot   # scripts/ 의 상위 = 프로젝트 루트
$CertFile  = Join-Path $AppDir "certs\localhost.pem"
$KeyFile   = Join-Path $AppDir "certs\localhost-key.pem"

Set-Location $AppDir

# --- 1. 인증서 확인 및 서버 모드 결정 ---
if ((Test-Path $CertFile) -and (Test-Path $KeyFile)) {
    $useHttps  = $true
    $port      = $HttpsPort
    $protocol  = "https"
    $uvicornArgs = @(
        "-m", "uvicorn", "main:app",
        "--host", "0.0.0.0",
        "--port", "$port",
        "--ssl-certfile", $CertFile,
        "--ssl-keyfile",  $KeyFile
    )
    Write-Host "[$AppName] HTTPS 모드로 배포합니다 (포트 $port)."
} else {
    $useHttps  = $false
    $port      = $HttpPort
    $protocol  = "http"
    $uvicornArgs = @(
        "-m", "uvicorn", "main:app",
        "--host", "0.0.0.0",
        "--port", "$port"
    )
    Write-Host "[$AppName] 인증서 없음 — HTTP 모드로 배포합니다 (포트 $port)."
    Write-Host "[$AppName] 경고: 화면 공유 기능은 HTTPS에서만 작동합니다."
}

# --- 2. 해당 포트를 점유 중인 기존 프로세스 종료 ---
Write-Host "[$AppName] 포트 $port 점유 프로세스를 확인합니다..."
$netstatLines = netstat -ano 2>$null | Select-String "[:.]$port\s"
$killedPids   = @()

foreach ($line in $netstatLines) {
    if ($line -match '\s+(\d+)\s*$') {
        $pid = [int]$Matches[1]
        if ($pid -gt 0 -and $pid -notin $killedPids) {
            try {
                Stop-Process -Id $pid -Force -ErrorAction Stop
                $killedPids += $pid
                Write-Host "[$AppName] PID $pid 종료 완료."
            } catch {
                Write-Host "[$AppName] PID $pid 종료 실패 (이미 종료됨): $_"
            }
        }
    }
}

if ($killedPids.Count -eq 0) {
    Write-Host "[$AppName] 포트 $port 를 사용 중인 프로세스가 없습니다."
}

Start-Sleep -Seconds 1

# --- 3. 새 서버 프로세스 시작 ---
Write-Host "[$AppName] 서버를 시작합니다..."
$process = Start-Process -FilePath "python" `
                         -ArgumentList $uvicornArgs `
                         -WorkingDirectory $AppDir `
                         -WindowStyle Hidden `
                         -PassThru

Write-Host "[$AppName] 프로세스 시작 (PID: $($process.Id))."

# 서버가 바인딩될 때까지 대기
Start-Sleep -Seconds 3

# --- 4. 헬스 체크 ---
Write-Host "[$AppName] 헬스 체크 중 (${protocol}://localhost:${port}/health)..."

# 자체 서명 인증서 검증 우회 (HTTPS 모드)
if ($useHttps) {
    [Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
}

$maxRetries = 5
$success    = $false

for ($i = 1; $i -le $maxRetries; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "${protocol}://localhost:${port}/health" `
                                      -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Host "[$AppName] 배포 성공. 헬스 체크 통과 ($($response.StatusCode))."
            $success = $true
            break
        }
    } catch {
        Write-Host "[$AppName] 헬스 체크 시도 $i/$maxRetries 실패. 재시도 중..."
        Start-Sleep -Seconds 2
    }
}

if (-not $success) {
    Write-Host "[$AppName] 배포 실패: 헬스 체크가 $maxRetries 회 모두 실패했습니다."
    exit 1
}
