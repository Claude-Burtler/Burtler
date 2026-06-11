# A/B Laptop Chat + Screen Share

FastAPI, WebSocket, WebRTC로 만든 내부망용 채팅/화면공유 예제입니다.

## 설치

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## HTTP 실행

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

B 노트북 접속:

```text
http://192.168.50.104:8000
```

## 내부망 HTTPS 실행

화면 공유를 B 노트북에서도 안정적으로 쓰려면 HTTPS가 필요합니다.

1. A 노트북에서 인증서 생성:

```bash
.venv\Scripts\python generate_https_cert.py
```

2. HTTPS 서버 실행:

```bash
uvicorn main:app --host 0.0.0.0 --port 8443 --ssl-certfile certs/localhost.pem --ssl-keyfile certs/localhost-key.pem
```

3. B 노트북에서 접속:

```text
https://192.168.50.104:8443
```

4. Chrome 경고가 뜨면 내부 테스트용으로 `고급` -> `계속 이동`을 선택합니다.

자체 서명 인증서라 경고는 뜹니다. 내부 테스트에서는 이 방식으로 충분하고, 운영 환경에서는 사내 CA 또는 정식 인증서를 써야 합니다.

## 사용법

1. A/B 노트북 모두 같은 HTTPS 주소로 접속합니다.
2. 각자 대화명을 설정합니다.
3. `화면 공유`를 누르고 네이버 지도나 카카오맵 화면을 선택합니다.
4. 상대 화면에서 자동으로 보이지 않으면 `공유 화면 보기`를 누릅니다.
5. 채팅에 지도 링크를 붙이면 `지도 링크 열기` 카드가 표시됩니다.

## API

- `GET /health`: 서버 상태 확인
- `GET /api/me`: 현재 접속자 정보 조회
- `PATCH /api/me`: 대화명 변경
- `GET /api/history`: 대화 기록 조회
- `DELETE /api/history`: 대화 기록 초기화
- `POST /api/chat`: HTTP 메시지 전송
- `WebSocket /ws/chat`: 채팅 및 화면 공유 신호 연결
