from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.connection import ConnectionManager
from app.models import (
    ChatMessage,
    ChatRequest,
    ClientProfile,
    ConnectionRecord,
    ScreenState,
)
from app.utils import normalize_host, now_iso

MAX_HISTORY = 200
_AUTHOR_LABELS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

chat_history: list[ChatMessage] = []
pinned_messages: list[str] = []
participant_names: dict[str, str] = {}
participant_counter: int = 0
screen_state = ScreenState()
manager = ConnectionManager()


def _next_author_label() -> str:
    global participant_counter
    participant_counter += 1
    idx = participant_counter - 1
    if idx < len(_AUTHOR_LABELS):
        return f"{_AUTHOR_LABELS[idx]} 노트북"
    return f"사용자 {participant_counter}"


def serialize_history() -> list[dict[str, Any]]:
    return [message.model_dump() for message in chat_history]


def profile_from_host(host: str | None, connection_id: str | None = None) -> ClientProfile:
    normalized_host = normalize_host(host)
    client_id = f"host:{normalized_host}"
    if client_id not in participant_names:
        participant_names[client_id] = _next_author_label()
    author = participant_names[client_id]
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
