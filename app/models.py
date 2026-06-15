from __future__ import annotations

from pydantic import BaseModel, Field


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
    pinned: bool = False


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
