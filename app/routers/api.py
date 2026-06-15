from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.models import ChatMessage, ChatRequest, ChatResponse, ClientProfile, NameUpdate
from app.store import state
from app.utils import normalize_host

router = APIRouter()


@router.get("/me", response_model=ClientProfile)
def get_me(request: Request) -> ClientProfile:
    host = request.client.host if request.client else None
    return state.profile_from_host(host)


@router.patch("/me", response_model=ClientProfile)
def update_me(payload: NameUpdate, request: Request) -> ClientProfile:
    host = request.client.host if request.client else None
    profile = state.profile_from_host(host)
    return state.update_author(profile, payload.author)


@router.get("/history", response_model=list[ChatMessage])
def get_history() -> list[ChatMessage]:
    return state.chat_history


@router.delete("/history")
async def clear_history(request: Request) -> dict[str, str]:
    host = request.client.host if request.client else None
    client_id = f"host:{normalize_host(host)}"

    for conn_id, record in list(state.manager.records.items()):
        if record.client_id == client_id:
            await state.manager.send(conn_id, {"type": "history", "messages": []})
            await state.manager.send(conn_id, {"type": "pinned", "message_ids": []})

    return {"status": "cleared"}


@router.post("/pin/{message_id}")
async def pin_message(message_id: str) -> dict[str, Any]:
    message = next((m for m in state.chat_history if m.id == message_id), None)
    if not message:
        return {"error": "메시지를 찾을 수 없습니다."}
    if message_id in state.pinned_messages:
        return {"status": "already_pinned"}
    state.pinned_messages.append(message_id)
    message.pinned = True
    await state.manager.broadcast({"type": "pinned", "message_ids": state.pinned_messages})
    return {"status": "pinned", "message_ids": state.pinned_messages}


@router.delete("/pin/{message_id}")
async def unpin_message(message_id: str) -> dict[str, Any]:
    if message_id not in state.pinned_messages:
        return {"status": "not_pinned"}
    state.pinned_messages.remove(message_id)
    message = next((m for m in state.chat_history if m.id == message_id), None)
    if message:
        message.pinned = False
    await state.manager.broadcast({"type": "pinned", "message_ids": state.pinned_messages})
    return {"status": "unpinned", "message_ids": state.pinned_messages}


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    host = request.client.host if request.client else None
    profile = state.update_author(state.profile_from_host(host), payload.author)
    message = state.add_message(payload, profile)
    await state.manager.broadcast({"type": "message", "message": message.model_dump()})
    return ChatResponse(message=message, history=state.chat_history)
