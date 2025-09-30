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
from fastapi.responses import PlainTextResponse
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger(__name__)

settings: Settings = get_settings()
configure_logging(settings.log_level, settings.log_directory, settings.log_retention_days)
app = FastAPI(title="mdai-controller", version="0.1.0")
manager = SessionManager(settings=settings)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> PlainTextResponse:
    """Catch-all exception handler to prevent application crashes."""
    logger.exception(f"Unhandled exception in {request.url.path}: {exc}")
    return PlainTextResponse(
        f"Internal server error: {str(exc)}", 
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors gracefully."""
    logger.warning(f"Validation error in {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)}
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    try:
        await manager.start()
        logger.info("Application started successfully")
    except Exception as e:
        logger.exception(f"Failed to start session manager: {e}")
        logger.error("Application startup failed - some features may not work")
        # Don't re-raise - allow app to start in degraded mode


@app.on_event("shutdown")
async def on_shutdown() -> None:
    try:
        await manager.stop()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.exception(f"Error during shutdown: {e}")


@app.get("/healthz")
async def healthcheck() -> JSONResponse:
    return JSONResponse({"status": "ok", "phase": manager.phase.value})


class PreviewToggleRequest(BaseModel):
    enabled: bool = True


class TofMockRequest(BaseModel):
    triggered: bool = True
    distance_mm: int = 345


@app.post("/debug/mock-tof")
async def mock_tof(payload: TofMockRequest) -> JSONResponse:
    """Mock ToF sensor for testing full session flow."""
    try:
        # Call the internal ToF trigger handler directly
        await manager._handle_tof_trigger(payload.triggered, payload.distance_mm)
        
        logger.info(f"🔧 Mock ToF: triggered={payload.triggered}, distance={payload.distance_mm}mm")
        return JSONResponse({
            "status": "ok",
            "triggered": payload.triggered,
            "distance_mm": payload.distance_mm,
            "current_phase": manager.phase.value
        })
    except Exception as e:
        logger.error(f"Failed to mock ToF: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.post("/debug/preview")
async def debug_preview_toggle(payload: PreviewToggleRequest) -> JSONResponse:
    """Enable/disable preview AND activate camera hardware for debugging."""
    try:
        # Set preview enabled
        preview_enabled = await manager.set_preview_enabled(payload.enabled)
        
        # ALSO activate/deactivate camera hardware (this starts liveness checks too!)
        await manager._realsense.set_hardware_active(payload.enabled, source="debug_preview")
        
        logger.info(f"🎥 Debug preview: camera hardware {'activated' if payload.enabled else 'deactivated'}")
        logger.info(f"🎥 Liveness heuristics will run automatically when camera is ON")
        
        return JSONResponse({
            "status": "enabled" if preview_enabled else "disabled",
            "hardware_active": payload.enabled,
            "liveness_active": payload.enabled
        })
    except Exception as e:
        logger.error(f"Failed to toggle preview: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.post("/debug/app-ready")
async def debug_app_ready(payload: dict[str, str] | None = Body(default=None)) -> JSONResponse:
    """Local helper to simulate the mobile app signalling readiness."""
    try:
        platform_id = (payload or {}).get("platform_id")
        acknowledged = await manager.mark_app_ready(platform_id=platform_id)
        status = "acknowledged" if acknowledged else "ignored"
        return JSONResponse({"status": status})
    except Exception as e:
        logger.error(f"Failed to mark app ready: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.get("/preview")
async def preview_stream() -> StreamingResponse:
    boundary = "frame"

    async def frame_iterator() -> AsyncIterator[bytes]:
        try:
            async for frame in manager.preview_frames():
                header = (
                    f"--{boundary}\r\n"
                    f"Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(frame)}\r\n\r\n"
                ).encode("ascii")
                yield header + frame + b"\r\n"
        except Exception as e:
            logger.error(f"Preview stream error: {e}")
            # Stream will end gracefully

    media_type = f"multipart/x-mixed-replace; boundary={boundary}"
    return StreamingResponse(frame_iterator(), media_type=media_type)


@app.websocket("/ws/ui")
async def ui_socket(ws: WebSocket) -> None:
    await ws.accept()
    queue = manager.register_ui()
    try:
        while True:
            try:
                event = await queue.get()
            except asyncio.CancelledError:
                break  # Clean shutdown
            
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
                logger.debug(f"WebSocket send failed (client disconnected): {e}")
                break
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass  # Clean shutdown
    except Exception as e:
        logger.error(f"Unexpected error in UI websocket: {e}")
    finally:
        manager.unregister_ui(queue)
        try:
            await ws.close()
        except Exception:
            pass

