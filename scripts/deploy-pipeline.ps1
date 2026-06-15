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

# 2. 변경사항 커밋 (있는 경우)
$dirty = git status --short
if ($dirty) {
    Write-Host "[deploy] 변경사항 감지. 자동 커밋 중..."
    git add -A

    $added    = @(git diff --cached --name-only --diff-filter=A)
    $modified = @(git diff --cached --name-only --diff-filter=M)
    $deleted  = @(git diff --cached --name-only --diff-filter=D)

    if ($added.Count -gt 0 -and $modified.Count -eq 0 -and $deleted.Count -eq 0) {
        $commitMsg = "feat: $($added -join ', ') 추가"
    } elseif ($deleted.Count -gt 0 -and $added.Count -eq 0 -and $modified.Count -eq 0) {
        $commitMsg = "chore: $($deleted -join ', ') 삭제"
    } elseif ($modified.Count -gt 0 -and $added.Count -eq 0 -and $deleted.Count -eq 0) {
        $commitMsg = "refactor: $($modified -join ', ') 수정"
    } else {
        $total = $added.Count + $modified.Count + $deleted.Count
        $commitMsg = "chore: ${total}개 파일 변경 (추가 $($added.Count), 수정 $($modified.Count), 삭제 $($deleted.Count))"
    }

    Write-Host "[deploy] 커밋 메시지: $commitMsg"
    git commit -m $commitMsg
} else {
    Write-Host "[deploy] 변경사항 없음. 기존 커밋으로 진행합니다."
}

# 3. 원격 push
Write-Host "[deploy] $branch 브랜치 push 중..."
git push -u origin $branch

# 4. feature → dev PR 생성 및 머지
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
