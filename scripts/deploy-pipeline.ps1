# Burtler deploy pipeline: feature → dev
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\deploy-pipeline.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# 1. Pre-flight check
$branch = git branch --show-current
if ($branch -eq "dev" -or $branch -eq "prd") {
    Write-Host "[deploy] Error: must be run from a feature branch. (current: $branch)"
    exit 1
}

# 2. Auto-commit if there are uncommitted changes
$dirty = git status --short
if ($dirty) {
    Write-Host "[deploy] Changes detected. Auto-committing..."
    git add -A

    $added    = @(git diff --cached --name-only --diff-filter=A)
    $modified = @(git diff --cached --name-only --diff-filter=M)
    $deleted  = @(git diff --cached --name-only --diff-filter=D)

    if ($added.Count -gt 0 -and $modified.Count -eq 0 -and $deleted.Count -eq 0) {
        $commitMsg = "feat: add $($added -join ', ')"
    } elseif ($deleted.Count -gt 0 -and $added.Count -eq 0 -and $modified.Count -eq 0) {
        $commitMsg = "chore: remove $($deleted -join ', ')"
    } elseif ($modified.Count -gt 0 -and $added.Count -eq 0 -and $deleted.Count -eq 0) {
        $commitMsg = "refactor: update $($modified -join ', ')"
    } else {
        $total = $added.Count + $modified.Count + $deleted.Count
        $commitMsg = "chore: $total files changed (added $($added.Count), modified $($modified.Count), deleted $($deleted.Count))"
    }

    Write-Host "[deploy] Commit message: $commitMsg"
    git commit -m $commitMsg
} else {
    Write-Host "[deploy] No changes. Proceeding with existing commits."
}

# 3. Push to remote
Write-Host "[deploy] Pushing $branch..."
git push -u origin $branch

# 4. Create and merge feature → dev PR
Write-Host "[deploy] Checking for existing PR ($branch → dev)..."
$existingPR = gh pr list --head $branch --base dev --json number --jq '.[0].number' 2>$null

if ($existingPR) {
    Write-Host "[deploy] Reusing existing PR #$existingPR."
    gh pr merge $existingPR --merge --delete-branch
} else {
    Write-Host "[deploy] Creating PR ($branch → dev)..."
    gh pr create --base dev --fill
    gh pr merge --merge --delete-branch
}

# Update local dev branch
git checkout dev
git pull

Write-Host ""
Write-Host "[deploy] Done: merged into dev."
