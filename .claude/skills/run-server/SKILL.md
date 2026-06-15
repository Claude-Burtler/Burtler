---
name: run-server
description: 로컬 개발 서버(HTTP, 포트 8000)를 백그라운드로 실행하고 헬스체크까지 확인
---

PowerShell 툴을 사용해 다음 명령을 실행하세요:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-dev.ps1
```

실행 후 출력 결과를 사용자에게 그대로 보여주세요.

- `서버 실행 중` + `접속 URL` 출력 → 성공
- `서버 시작 실패` 출력 → 실패 원인을 설명하세요
