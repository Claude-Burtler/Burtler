from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app import store
from app.models import ChatRequest, ChatMessage, ChatResponse, ClientProfile, NameUpdate

router = APIRouter()


@router.get("/me", response_model=ClientProfile)
def get_me(request: Request) -> ClientProfile:
    host = request.client.host if request.client else None
    return store.profile_from_host(host)


@router.patch("/me", response_model=ClientProfile)
def update_me(payload: NameUpdate, request: Request) -> ClientProfile:
    host = request.client.host if request.client else None
    profile = store.profile_from_host(host)
    return store.update_author(profile, payload.author)


@router.get("/history", response_model=list[ChatMessage])
def get_history() -> list[ChatMessage]:
    return store.chat_history


@router.delete("/history")
async def clear_history() -> dict[str, str]:
    store.chat_history.clear()
    store.pinned_messages.clear()
    await store.manager.broadcast({"type": "history", "messages": []})
    await store.manager.broadcast({"type": "pinned", "message_ids": []})
    return {"status": "cleared"}


@router.post("/pin/{message_id}")
async def pin_message(message_id: str) -> dict[str, Any]:
    message = next((m for m in store.chat_history if m.id == message_id), None)
    if not message:
        return {"error": "메시지를 찾을 수 없습니다."}
    if message_id in store.pinned_messages:
        return {"status": "already_pinned"}
    store.pinned_messages.append(message_id)
    message.pinned = True
    await store.manager.broadcast({"type": "pinned", "message_ids": store.pinned_messages})
    return {"status": "pinned", "message_ids": store.pinned_messages}


@router.delete("/pin/{message_id}")
async def unpin_message(message_id: str) -> dict[str, Any]:
    if message_id not in store.pinned_messages:
        return {"status": "not_pinned"}
    store.pinned_messages.remove(message_id)
    message = next((m for m in store.chat_history if m.id == message_id), None)
    if message:
        message.pinned = False
    await store.manager.broadcast({"type": "pinned", "message_ids": store.pinned_messages})
    return {"status": "unpinned", "message_ids": store.pinned_messages}


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    host = request.client.host if request.client else None
    profile = store.update_author(store.profile_from_host(host), payload.author)
    message = store.add_message(payload, profile)
    await store.manager.broadcast({"type": "message", "message": message.model_dump()})
    return ChatResponse(message=message, history=store.chat_history)
