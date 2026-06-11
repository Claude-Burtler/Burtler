from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
from pathlib import Path
import socket
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MAX_HISTORY = 200


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    author: str | None = Field(default=None, max_length=40)


class NameUpdate(BaseModel):
    author: str = Field(..., min_length=1, max_length=40)


class ChatMessage(BaseModel):
    id: str
    author: str
    client_id: str
    host: str
    text: str
    created_at: str


class ChatResponse(BaseModel):
    message: ChatMessage
    history: list[ChatMessage]


class ClientProfile(BaseModel):
    client_id: str
    connection_id: str | None = None
    author: str
    host: str


class ScreenState(BaseModel):
    active: bool = False
    presenter_connection_id: str | None = None
    presenter_client_id: str | None = None
    presenter_name: str | None = None


class ConnectionRecord(BaseModel):
    connection_id: str
    client_id: str
    author: str
    host: str


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.records: dict[str, ConnectionRecord] = {}

    async def connect(self, websocket: WebSocket, record: ConnectionRecord) -> None:
        await websocket.accept()
        self.active_connections[record.connection_id] = websocket
        self.records[record.connection_id] = record

    def disconnect(self, connection_id: str) -> None:
        self.active_connections.pop(connection_id, None)
        self.records.pop(connection_id, None)

    async def send(self, connection_id: str, payload: dict[str, Any]) -> None:
        websocket = self.active_connections.get(connection_id)

        if websocket is None:
            return

        try:
            await websocket.send_json(payload)
        except RuntimeError:
            self.disconnect(connection_id)

    async def broadcast(
        self,
        payload: dict[str, Any],
        exclude_connection_id: str | None = None,
    ) -> None:
        for connection_id in list(self.active_connections):
            if connection_id == exclude_connection_id:
                continue

            await self.send(connection_id, payload)


app = FastAPI(title="A/B Laptop Chat + Screen Share", version="3.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

chat_history: list[ChatMessage] = []
participant_names: dict[str, str] = {}
screen_state = ScreenState()
manager = ConnectionManager()


def local_hosts() -> set[str]:
    hosts = {"127.0.0.1", "::1", "localhost"}

    try:
        hostname = socket.gethostname()
        hosts.update(socket.gethostbyname_ex(hostname)[2])
    except OSError:
        pass

    return hosts


LOCAL_HOSTS = local_hosts()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def serialize_history() -> list[dict[str, Any]]:
    return [message.model_dump() for message in chat_history]


def normalize_host(host: str | None) -> str:
    if not host:
        return "unknown"

    normalized = host.removeprefix("::ffff:")

    try:
        if ipaddress.ip_address(normalized).is_loopback:
            return "server-local"
    except ValueError:
        pass

    if normalized in LOCAL_HOSTS:
        return "server-local"

    return normalized


def default_author(host: str) -> str:
    if host == "server-local":
        return "A 노트북"

    return "B 노트북"


def profile_from_host(host: str | None, connection_id: str | None = None) -> ClientProfile:
    normalized_host = normalize_host(host)
    client_id = f"host:{normalized_host}"
    author = participant_names.setdefault(client_id, default_author(normalized_host))

    return ClientProfile(
        client_id=client_id,
        connection_id=connection_id,
        author=author,
        host=normalized_host,
    )


def update_author(profile: ClientProfile, author: str | None) -> ClientProfile:
    cleaned_author = (author or "").strip()

    if cleaned_author:
        participant_names[profile.client_id] = cleaned_author
        profile.author = cleaned_author

    return profile


def add_message(payload: ChatRequest, profile: ClientProfile) -> ChatMessage:
    message = ChatMessage(
        id=str(uuid4()),
        author=participant_names.get(profile.client_id, profile.author),
        client_id=profile.client_id,
        host=profile.host,
        text=payload.message.strip(),
        created_at=now_iso(),
    )
    chat_history.append(message)

    if len(chat_history) > MAX_HISTORY:
        del chat_history[: len(chat_history) - MAX_HISTORY]

    return message


def stop_screen_share_if_presenter(connection_id: str) -> bool:
    if screen_state.presenter_connection_id != connection_id:
        return False

    screen_state.active = False
    screen_state.presenter_connection_id = None
    screen_state.presenter_client_id = None
    screen_state.presenter_name = None
    return True


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/me", response_model=ClientProfile)
def get_me(request: Request) -> ClientProfile:
    host = request.client.host if request.client else None
    return profile_from_host(host)


@app.patch("/api/me", response_model=ClientProfile)
def update_me(payload: NameUpdate, request: Request) -> ClientProfile:
    host = request.client.host if request.client else None
    profile = profile_from_host(host)
    return update_author(profile, payload.author)


@app.get("/api/history", response_model=list[ChatMessage])
def get_history() -> list[ChatMessage]:
    return chat_history


@app.delete("/api/history")
async def clear_history() -> dict[str, str]:
    chat_history.clear()
    await manager.broadcast({"type": "history", "messages": []})
    return {"status": "cleared"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    host = request.client.host if request.client else None
    profile = update_author(profile_from_host(host), payload.author)
    message = add_message(payload, profile)
    await manager.broadcast({"type": "message", "message": message.model_dump()})
    return ChatResponse(message=message, history=chat_history)


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    host = websocket.client.host if websocket.client else None
    connection_id = str(uuid4())
    profile = profile_from_host(host, connection_id)
    record = ConnectionRecord(
        connection_id=connection_id,
        client_id=profile.client_id,
        author=profile.author,
        host=profile.host,
    )

    await manager.connect(websocket, record)
    await websocket.send_json({"type": "profile", "profile": profile.model_dump()})
    await websocket.send_json({"type": "history", "messages": serialize_history()})
    await websocket.send_json({"type": "screen-state", "state": screen_state.model_dump()})

    try:
        while True:
            raw_payload = await websocket.receive_json()
            event_type = raw_payload.get("type", "chat")

            if event_type == "chat":
                try:
                    payload = ChatRequest.model_validate(raw_payload)
                except ValidationError:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "메시지와 대화명을 확인하세요.",
                        }
                    )
                    continue

                update_author(profile, payload.author)
                message = add_message(payload, profile)
                await manager.broadcast({"type": "message", "message": message.model_dump()})
                continue

            if event_type == "screen-start":
                screen_state.active = True
                screen_state.presenter_connection_id = connection_id
                screen_state.presenter_client_id = profile.client_id
                screen_state.presenter_name = participant_names.get(profile.client_id, profile.author)
                await manager.broadcast({"type": "screen-state", "state": screen_state.model_dump()})
                continue

            if event_type == "screen-stop":
                if stop_screen_share_if_presenter(connection_id):
                    await manager.broadcast({"type": "screen-state", "state": screen_state.model_dump()})
                continue

            if event_type == "screen-watch":
                presenter_id = screen_state.presenter_connection_id

                if not screen_state.active or not presenter_id:
                    await websocket.send_json({"type": "screen-state", "state": screen_state.model_dump()})
                    continue

                await manager.send(
                    presenter_id,
                    {
                        "type": "screen-watch",
                        "viewer": profile.model_dump(),
                    },
                )
                continue

            if event_type == "webrtc-signal":
                to_connection_id = raw_payload.get("to")

                if not isinstance(to_connection_id, str):
                    continue

                await manager.send(
                    to_connection_id,
                    {
                        "type": "webrtc-signal",
                        "from": connection_id,
                        "signal": raw_payload.get("signal"),
                    },
                )
                continue

            if event_type == "screen-frame":
                if screen_state.presenter_connection_id != connection_id:
                    continue

                frame = raw_payload.get("frame")
                if not isinstance(frame, str) or not frame.startswith("data:image/"):
                    continue

                await manager.broadcast(
                    {
                        "type": "screen-frame",
                        "from": connection_id,
                        "frame": frame,
                    },
                    exclude_connection_id=connection_id,
                )
                continue

            await websocket.send_json({"type": "error", "message": "알 수 없는 이벤트입니다."})
    except WebSocketDisconnect:
        manager.disconnect(connection_id)

        if stop_screen_share_if_presenter(connection_id):
            await manager.broadcast({"type": "screen-state", "state": screen_state.model_dump()})
