---
name: check-actions
description: prd 브랜치 최신 GitHub Actions run 상태 확인, 실패 시 로그 분석 및 원인 설명
---

prd 브랜치의 최신 GitHub Actions run을 확인합니다. **상태 조회 → 대기/분석 → 재실행 여부** 순서로 진행합니다.

## 1단계: 최신 run 조회

```bash
gh run list --branch prd --limit 5 --json databaseId,status,conclusion,displayTitle,createdAt
```

가장 최근 run(`createdAt` 기준)의 `status`에 따라 분기합니다:

| status | conclusion | 처리 |
|--------|------------|------|
| `completed` | `success` | "최근 배포 성공 ✓" + 완료 시각 출력 후 종료 |
| `completed` | `failure` | 3단계로 이동 |
| `in_progress` | — | 2단계로 이동 |
| `queued` | — | 2단계로 이동 |

## 2단계: 진행 중인 run 완료 대기

`in_progress` 또는 `queued` 상태이면 완료까지 대기합니다:

```bash
gh run watch <databaseId>
```

완료 후 `conclusion`이 `success`이면 종료, `failure`이면 3단계로 이동합니다.

## 3단계: 실패 로그 분석

```bash
gh run view <databaseId> --log-failed
```

로그를 읽고 실패 원인을 파악해 사용자에게 설명합니다:

- **Python 문법 오류** (`SyntaxError`, `compileall`): 해당 파일과 라인 번호 안내
- **pip install 실패**: 패키지명 및 버전 충돌 원인 안내
- **헬스체크 실패** (curl 200 미응답): uvicorn 시작 실패 가능성 안내, Task Scheduler 로그 확인 방법 안내
- **PowerShell 실행 오류**: 스크립트 경로 또는 권한 문제 안내
- **기타**: 관련 로그 섹션 그대로 출력

## 4단계: 재실행 여부 확인 (실패 시)

실패 원인을 설명한 후, 원인을 수정하지 않아도 재실행이 의미 있는 경우(일시적 오류 등) 사용자에게 재실행 여부를 묻습니다:

```bash
gh run rerun <databaseId> --failed-only
```

## 주의사항

- prd 브랜치에 run이 없으면 "아직 배포 이력이 없습니다"로 안내합니다
- `gh run watch`는 터미널에서 실시간 진행 상황을 표시합니다 (background 사용 금지)
