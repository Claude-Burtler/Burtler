from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.connection import ConnectionManager
from app.models import (
    ChatMessage,
    ChatRequest,
    ClientProfile,
    ScreenState,
)
from app.utils import normalize_host, now_iso


class AppState:
    MAX_HISTORY = 200
    _AUTHOR_LABELS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

    def __init__(self) -> None:
        self.chat_history: list[ChatMessage] = []
        self.pinned_messages: list[str] = []
        self.participant_names: dict[str, str] = {}
        self.participant_counter: int = 0
        self.screen_state = ScreenState()
        self.manager = ConnectionManager()

    def _next_author_label(self) -> str:
        self.participant_counter += 1
        idx = self.participant_counter - 1
        if idx < len(self._AUTHOR_LABELS):
            return f"{self._AUTHOR_LABELS[idx]} 노트북"
        return f"사용자 {self.participant_counter}"

    def serialize_history(self) -> list[dict[str, Any]]:
        return [message.model_dump() for message in self.chat_history]

    def profile_from_host(self, host: str | None, connection_id: str | None = None) -> ClientProfile:
        normalized_host = normalize_host(host)
        client_id = f"host:{normalized_host}"
        if client_id not in self.participant_names:
            self.participant_names[client_id] = self._next_author_label()
        author = self.participant_names[client_id]
        return ClientProfile(
            client_id=client_id,
            connection_id=connection_id,
            author=author,
            host=normalized_host,
        )

    def update_author(self, profile: ClientProfile, author: str | None) -> ClientProfile:
        cleaned_author = (author or "").strip()
        if cleaned_author:
            self.participant_names[profile.client_id] = cleaned_author
            profile.author = cleaned_author
        return profile

    def add_message(self, payload: ChatRequest, profile: ClientProfile) -> ChatMessage:
        message = ChatMessage(
            id=str(uuid4()),
            author=self.participant_names.get(profile.client_id, profile.author),
            client_id=profile.client_id,
            host=profile.host,
            text=payload.message.strip(),
            created_at=now_iso(),
        )
        self.chat_history.append(message)
        if len(self.chat_history) > self.MAX_HISTORY:
            del self.chat_history[: len(self.chat_history) - self.MAX_HISTORY]
        return message

    def stop_screen_share_if_presenter(self, connection_id: str) -> bool:
        if self.screen_state.presenter_connection_id != connection_id:
            return False
        self.screen_state.active = False
        self.screen_state.presenter_connection_id = None
        self.screen_state.presenter_client_id = None
        self.screen_state.presenter_name = None
        return True


state = AppState()
