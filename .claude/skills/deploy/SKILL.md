---
name: deploy
description: 현재 feature 브랜치를 dev까지 PR 생성/머지하는 배포 파이프라인
---

PowerShell 툴을 사용해 다음 명령을 실행하세요:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-pipeline.ps1
```

실행 후 출력 결과를 사용자에게 그대로 보여주세요.

- `배포 완료` 출력 → 성공
- `오류:` 출력 → 실패 원인을 분석해 사용자에게 설명하세요
