"""FastAPI entry-point for the mdai controller."""
from __future__ import annotations

import logging
from typing import AsyncIterator

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .config import Settings, get_settings
from .logging_config import configure_logging
from .session_manager import SessionManager

logger = logging.getLogger(__name__)

settings: Settings = get_settings()
configure_logging(settings.log_level, settings.log_directory, settings.log_retention_days)
app = FastAPI(title="mdai-controller", version="0.1.0")
manager = SessionManager(settings=settings)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    await manager.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await manager.stop()


@app.get("/healthz")
async def healthcheck() -> JSONResponse:
    return JSONResponse({"status": "ok", "phase": manager.phase.value})


@app.post("/debug/trigger")
async def debug_trigger() -> JSONResponse:
    await manager.trigger_debug_session()
    return JSONResponse({"status": "scheduled"})


class TofTriggerRequest(BaseModel):
    triggered: bool = True
    distance_mm: int | None = None


class TofBypassRequest(BaseModel):
    enabled: bool = True


class PreviewToggleRequest(BaseModel):
    enabled: bool = True


@app.post("/debug/tof-trigger")
async def debug_tof_trigger(payload: TofTriggerRequest) -> JSONResponse:
    await manager.simulate_tof_trigger(triggered=payload.triggered, distance_mm=payload.distance_mm)
    return JSONResponse({"status": "ok"})


@app.post("/debug/tof-bypass")
async def debug_tof_bypass(payload: TofBypassRequest) -> JSONResponse:
    await manager.set_tof_bypass(payload.enabled)
    return JSONResponse({"status": "enabled" if payload.enabled else "disabled"})


@app.post("/debug/preview")
async def debug_preview_toggle(payload: PreviewToggleRequest) -> JSONResponse:
    enabled = await manager.set_preview_enabled(payload.enabled)
    return JSONResponse({"status": "enabled" if enabled else "disabled"})


@app.post("/debug/app-ready")
async def debug_app_ready(payload: dict[str, str] | None = Body(default=None)) -> JSONResponse:
    """Local helper to simulate the mobile app signalling readiness."""

    platform_id = (payload or {}).get("platform_id")
    acknowledged = await manager.mark_app_ready(platform_id=platform_id)
    status = "acknowledged" if acknowledged else "ignored"
    return JSONResponse({"status": status})


@app.get("/preview")
async def preview_stream() -> StreamingResponse:
    boundary = "frame"

    async def frame_iterator() -> AsyncIterator[bytes]:
        async for frame in manager.preview_frames():
            header = (
                f"--{boundary}\r\n"
                f"Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(frame)}\r\n\r\n"
            ).encode("ascii")
            yield header + frame + b"\r\n"

    media_type = f"multipart/x-mixed-replace; boundary={boundary}"
    return StreamingResponse(frame_iterator(), media_type=media_type)


@app.websocket("/ws/ui")
async def ui_socket(ws: WebSocket) -> None:
    await ws.accept()
    queue = manager.register_ui()
    try:
        while True:
            event = await queue.get()
            payload = {
                "type": event.type,
                "phase": event.phase.value,
                "data": event.data,
            }
            if event.error:
                payload["error"] = event.error
            try:
                await ws.send_json(payload)
            except Exception as e:
                # WebSocket closed, break out of loop
                logger.warning(f"WebSocket send failed: {e}")
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.unregister_ui(queue)
        try:
            await ws.close()
        except Exception:
            pass
