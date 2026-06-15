from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app import store
from app.models import ChatRequest, ConnectionRecord

router = APIRouter()


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    host = websocket.client.host if websocket.client else None
    connection_id = str(uuid4())
    profile = store.profile_from_host(host, connection_id)
    record = ConnectionRecord(
        connection_id=connection_id,
        client_id=profile.client_id,
        author=profile.author,
        host=profile.host,
    )

    await store.manager.connect(websocket, record)
    await websocket.send_json({"type": "profile", "profile": profile.model_dump()})
    await websocket.send_json({"type": "history", "messages": store.serialize_history()})
    await websocket.send_json({"type": "pinned", "message_ids": store.pinned_messages})
    await websocket.send_json({"type": "screen-state", "state": store.screen_state.model_dump()})

    try:
        while True:
            raw_payload = await websocket.receive_json()
            event_type = raw_payload.get("type", "chat")

            if event_type == "chat":
                try:
                    payload = ChatRequest.model_validate(raw_payload)
                except ValidationError:
                    await websocket.send_json({"type": "error", "message": "메시지와 대화명을 확인하세요."})
                    continue
                store.update_author(profile, payload.author)
                message = store.add_message(payload, profile)
                await store.manager.broadcast({"type": "message", "message": message.model_dump()})
                continue

            if event_type == "screen-start":
                store.screen_state.active = True
                store.screen_state.presenter_connection_id = connection_id
                store.screen_state.presenter_client_id = profile.client_id
                store.screen_state.presenter_name = store.participant_names.get(profile.client_id, profile.author)
                await store.manager.broadcast({"type": "screen-state", "state": store.screen_state.model_dump()})
                continue

            if event_type == "screen-stop":
                if store.stop_screen_share_if_presenter(connection_id):
                    await store.manager.broadcast({"type": "screen-state", "state": store.screen_state.model_dump()})
                continue

            if event_type == "screen-watch":
                presenter_id = store.screen_state.presenter_connection_id
                if not store.screen_state.active or not presenter_id:
                    await websocket.send_json({"type": "screen-state", "state": store.screen_state.model_dump()})
                    continue
                await store.manager.send(presenter_id, {"type": "screen-watch", "viewer": profile.model_dump()})
                continue

            if event_type == "webrtc-signal":
                to_connection_id = raw_payload.get("to")
                if not isinstance(to_connection_id, str):
                    continue
                await store.manager.send(
                    to_connection_id,
                    {"type": "webrtc-signal", "from": connection_id, "signal": raw_payload.get("signal")},
                )
                continue

            if event_type == "screen-frame":
                if store.screen_state.presenter_connection_id != connection_id:
                    continue
                frame = raw_payload.get("frame")
                if not isinstance(frame, str) or not frame.startswith("data:image/"):
                    continue
                await store.manager.broadcast(
                    {"type": "screen-frame", "from": connection_id, "frame": frame},
                    exclude_connection_id=connection_id,
                )
                continue

            await websocket.send_json({"type": "error", "message": "알 수 없는 이벤트입니다."})
    except WebSocketDisconnect:
        store.manager.disconnect(connection_id)
        if store.stop_screen_share_if_presenter(connection_id):
            await store.manager.broadcast({"type": "screen-state", "state": store.screen_state.model_dump()})
