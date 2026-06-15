# Burtler 배포 파이프라인: feature → dev
# 사용: powershell -ExecutionPolicy Bypass -File .\scripts\deploy-pipeline.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# 1. 사전 확인
$branch = git branch --show-current
if ($branch -eq "dev" -or $branch -eq "prd") {
    Write-Host "[deploy] 오류: feature 브랜치에서만 실행 가능합니다. (현재: $branch)"
    exit 1
}

$dirty = git status --short
if ($dirty) {
    Write-Host "[deploy] 오류: 미커밋 변경사항이 있습니다. 커밋 후 다시 실행해주세요."
    git status --short
    exit 1
}

Write-Host "[deploy] 배포 시작: $branch → dev"

# 2. feature → dev PR 생성 및 머지
Write-Host "[deploy] feature → dev PR 확인 중..."
$existingPR = gh pr list --head $branch --base dev --json number --jq '.[0].number' 2>$null

if ($existingPR) {
    Write-Host "[deploy] 기존 PR #$existingPR 재사용."
    gh pr merge $existingPR --merge --delete-branch
} else {
    Write-Host "[deploy] PR 생성 중 ($branch → dev)..."
    gh pr create --base dev --fill
    gh pr merge --merge --delete-branch
}

# 로컬 dev 브랜치 업데이트
git checkout dev
git pull

Write-Host ""
Write-Host "[deploy] 배포 완료: dev 브랜치에 머지되었습니다."
