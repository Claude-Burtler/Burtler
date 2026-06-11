# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

내부망 전용 실시간 채팅 + 화면 공유 앱. FastAPI + WebSocket(채팅) + WebRTC(P2P 화면 공유)로 구성. 두 노트북 간 연결을 가정하여 A/B 노트북으로 자동 구분.

## 실행 명령어

**의존성 설치:**
```bash
pip install -r requirements.txt
```

**HTTP 개발 서버 (로컬 테스트):**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**HTTPS 서버 (화면 공유 필수 — 브라우저 보안 정책):**
```bash
# 1단계: 인증서 생성 (최초 1회 또는 인증서 만료 시)
python generate_https_cert.py

# 2단계: HTTPS로 실행
uvicorn main:app --host 0.0.0.0 --port 8443 --ssl-certfile certs/localhost.pem --ssl-keyfile certs/localhost-key.pem
```

**문법 검사 (CI와 동일):**
```bash
python -m compileall .
```

## 브랜치 전략

`feature/*` → `dev` (PR) → `prd` (배포 트리거)

- CI/CD는 `prd` 브랜치 push 시에만 실행 (GitHub Actions, 자체 호스팅 Windows x64 러너)
- `scripts/deploy.ps1` — 미작성 상태, 추후 구현 예정. Actions에서 참조하나 현재 파이프라인 마지막 단계는 실패함

## 아키텍처 특이사항

**상태 관리:** 모든 상태(`chat_history`, `participant_names`, `screen_state`)가 메모리에만 저장됨. 서버 재시작 시 데이터 소멸.

**WebRTC 폴백:** WebRTC P2P 연결 실패 시 JPEG 프레임 릴레이(700ms 인터벌)로 자동 전환. 두 경로 모두 `main.py`에서 처리.

**호스트 자동 구분:** 서버 접속 IP를 기준으로 `localhost`/IPv6 loopback이면 "A 노트북", 그 외이면 "B 노트북"으로 자동 지정. `main.py`의 `is_local_host()` 참고.

**화면 공유 HTTPS 필수:** 브라우저의 `getDisplayMedia()` API는 HTTPS 또는 localhost에서만 동작. 원격 접속 시 반드시 HTTPS로 실행해야 함.

**채팅 기록 제한:** `MAX_HISTORY = 200` (`main.py` 상단). 초과 시 오래된 항목 자동 삭제.

## 코딩 컨벤션

- Python: 타입 힌트 필수, Pydantic BaseModel로 요청/응답 스키마 정의
- 메시지 길이 제한: 본문 1,000자, 저자명 40자 (`main.py`의 Pydantic 모델 참고)
- 프론트엔드: 라이브러리 없는 Vanilla JS 유지
