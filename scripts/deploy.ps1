# Burtler 배포 스크립트
# prd 브랜치 push 시 GitHub Actions(자체 호스팅 Windows x64)에서 자동 실행
# 수동 실행: powershell -ExecutionPolicy Bypass -File .\scripts\deploy.ps1

param(
    [int]$HttpsPort = 8443,
    [int]$HttpPort  = 8000
)

$AppName  = "Burtler"
$TaskName = "Burtler-Server"
$AppDir   = Split-Path $PSScriptRoot   # scripts/ 의 상위 = 프로젝트 루트
$CertFile = Join-Path $AppDir "certs\localhost.pem"
$KeyFile  = Join-Path $AppDir "certs\localhost-key.pem"

# SYSTEM 계정은 PATH가 달라 "python"을 못 찾으므로 전체 경로를 사용
$Python = (Get-Command python -ErrorAction Stop).Source
Write-Host "[$AppName] Python 경로: $Python"

# --- 1. 인증서 확인 및 서버 모드 결정 ---
if ((Test-Path $CertFile) -and (Test-Path $KeyFile)) {
    $useHttps = $true
    $port     = $HttpsPort
    $protocol = "https"
    $uvicornCmd = "`"$Python`" -m uvicorn main:app --host 0.0.0.0 --port $port --ssl-certfile `"$CertFile`" --ssl-keyfile `"$KeyFile`""
    Write-Host "[$AppName] HTTPS 모드로 배포합니다 (포트 $port)."
} else {
    $useHttps = $false
    $port     = $HttpPort
    $protocol = "http"
    $uvicornCmd = "`"$Python`" -m uvicorn main:app --host 0.0.0.0 --port $port"
    Write-Host "[$AppName] 인증서 없음 — HTTP 모드로 배포합니다 (포트 $port)."
    Write-Host "[$AppName] 경고: 화면 공유 기능은 HTTPS에서만 작동합니다."
}

# --- 2. 기존 포트 점유 프로세스 종료 ---
Write-Host "[$AppName] 포트 $port 점유 프로세스를 확인합니다..."
$killedPids = @()

netstat -ano 2>$null | Select-String "[:.]$port\s" | ForEach-Object {
    if ($_ -match '\s+(\d+)\s*$') {
        $p = [int]$Matches[1]
        if ($p -gt 0 -and $p -notin $killedPids) {
            try {
                Stop-Process -Id $p -Force -ErrorAction Stop
                $killedPids += $p
                Write-Host "[$AppName] PID $p 종료 완료."
            } catch {
                Write-Host "[$AppName] PID $p 이미 종료됨."
            }
        }
    }
}

if ($killedPids.Count -eq 0) {
    Write-Host "[$AppName] 포트 $port 를 사용 중인 프로세스가 없습니다."
}

# --- 3. 기존 작업 스케줄러 태스크 제거 ---
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Stop-ScheduledTask  -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "[$AppName] 기존 스케줄러 태스크 제거 완료."
}

Start-Sleep -Seconds 1

# --- 4. 작업 스케줄러로 서버 등록 및 시작 ---
# GitHub Actions 러너가 종료해도 프로세스가 유지되도록 Task Scheduler 사용
Write-Host "[$AppName] 작업 스케줄러에 서버를 등록합니다..."

$action  = New-ScheduledTaskAction -Execute "powershell.exe" `
               -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -Command `"Set-Location '$AppDir'; $uvicornCmd`"" `
               -WorkingDirectory $AppDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName `
                       -Action $action `
                       -Trigger $trigger `
                       -Settings $settings `
                       -Principal $principal `
                       -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName
Write-Host "[$AppName] 서버 시작 요청 완료."

# 서버가 바인딩될 때까지 대기
Start-Sleep -Seconds 5

# --- 5. 헬스 체크 ---
# Invoke-WebRequest 대신 curl.exe 사용:
# ServicePointManager 콜백은 프로세스 전체에 적용되어
# Actions 러너의 GitHub 통신까지 차단하는 부작용이 있음
Write-Host "[$AppName] 헬스 체크 중 (${protocol}://localhost:${port}/health)..."

$maxRetries = 5
$success    = $false

for ($i = 1; $i -le $maxRetries; $i++) {
    # -k: 자체 서명 인증서 허용, -s: 진행바 숨김, --max-time 5: 타임아웃
    $statusCode = curl.exe -k -s -o NUL -w "%{http_code}" --max-time 5 "${protocol}://localhost:${port}/health" 2>$null
    if ($statusCode -eq "200") {
        Write-Host "[$AppName] 배포 성공. 헬스 체크 통과 ($statusCode)."
        $success = $true
        break
    }
    Write-Host "[$AppName] 헬스 체크 시도 $i/$maxRetries 실패 (응답: $statusCode). 재시도 중..."
    Start-Sleep -Seconds 2
}

if (-not $success) {
    Write-Host "[$AppName] 배포 실패: 헬스 체크가 $maxRetries 회 모두 실패했습니다."
    exit 1
}
