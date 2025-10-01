"""FastAPI entry-point for the mdai controller."""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator
import psutil

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .config import Settings, get_settings
from .logging_config import configure_logging
from .session_manager import SessionManager
from .sensors.webcam_service import WebcamService
from fastapi.responses import PlainTextResponse
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
import asyncio

logger = logging.getLogger(__name__)

settings: Settings = get_settings()
configure_logging(settings.log_level, settings.log_directory, settings.log_retention_days)
app = FastAPI(title="mdai-controller", version="0.1.0")
manager = SessionManager(settings=settings)

# Webcam service for debug preview (laptop camera)
webcam_service = WebcamService(camera_id=0)
active_camera_source: str = "webcam"  # "realsense" or "webcam" - default to webcam for easier testing

# Inject webcam service into manager for progress updates
manager._webcam_service = webcam_service

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
        await webcam_service.start()
        logger.info("Application started successfully (including webcam service)")
    except Exception as e:
        logger.exception(f"Failed to start services: {e}")
        logger.error("Application startup failed - some features may not work")
        # Don't re-raise - allow app to start in degraded mode


@app.on_event("shutdown")
async def on_shutdown() -> None:
    try:
        await manager.stop()
        await webcam_service.stop()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.exception(f"Error during shutdown: {e}")


@app.get("/healthz")
async def healthcheck() -> JSONResponse:
    return JSONResponse({"status": "ok", "phase": manager.phase.value})


@app.get("/debug/performance")
async def debug_performance() -> JSONResponse:
    """Get real-time CPU and memory usage."""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        return JSONResponse({
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": round(memory.percent, 1),
            "memory_used_mb": round(memory.used / (1024 * 1024), 1),
            "memory_total_mb": round(memory.total / (1024 * 1024), 1)
        })
    except Exception as e:
        logger.error(f"Performance monitoring error: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


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
        # Set preview enabled (camera hardware stays controlled by session flow)
        preview_enabled = await manager.set_preview_enabled(payload.enabled)

        try:
            await manager._realsense.set_hardware_active(payload.enabled, source="debug_preview")
            logger.info(
                "🎥 Debug preview %s (RealSense %s)",
                "enabled" if payload.enabled else "disabled",
                "activated" if payload.enabled else "deactivated",
            )
        except Exception as exc:
            logger.exception("Failed to toggle debug preview hardware: %s", exc)
            try:
                await manager._realsense.set_hardware_active(False, source="debug_preview")
            except Exception:
                logger.warning("Failed to ensure debug preview hardware release after error")
            await manager.set_preview_enabled(False)
            return JSONResponse(
                {"status": "error", "message": "Unable to toggle camera hardware"},
                status_code=500,
            )
        
        return JSONResponse({
            "status": "enabled" if preview_enabled else "disabled",
            "hardware_active": preview_enabled,
            "liveness_active": preview_enabled
        })
    except Exception as e:
        logger.error(f"Failed to toggle preview: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


class PreviewModeRequest(BaseModel):
    mode: str = "normal"  # "normal" or "eye_tracking"


@app.post("/debug/preview-mode")
async def debug_preview_mode(payload: PreviewModeRequest) -> JSONResponse:
    """Toggle preview rendering mode between normal and eye tracking."""
    try:
        # Set mode on active camera source
        if active_camera_source == "webcam":
            mode = await webcam_service.set_preview_mode(payload.mode)
        else:
            mode = await manager._realsense.set_preview_mode(payload.mode)
        
        logger.info(f"👁️ Preview mode changed to: {mode} (source: {active_camera_source})")
        
        return JSONResponse({
            "status": "ok",
            "mode": mode,
            "camera_source": active_camera_source
        })
    except Exception as e:
        logger.error(f"Failed to set preview mode: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


class CameraSourceRequest(BaseModel):
    source: str = "realsense"  # "realsense" or "webcam"


@app.post("/debug/camera-source")
async def debug_camera_source(payload: CameraSourceRequest) -> JSONResponse:
    """Switch between RealSense and webcam camera sources."""
    global active_camera_source
    
    try:
        if payload.source not in ("realsense", "webcam"):
            return JSONResponse(
                {"status": "error", "message": f"Invalid source: {payload.source}"},
                status_code=400
            )
        
        old_source = active_camera_source
        active_camera_source = payload.source
        
        logger.info(f"📷 Camera source switched: {old_source} → {active_camera_source}")
        
        return JSONResponse({
            "status": "ok",
            "camera_source": active_camera_source,
            "previous_source": old_source
        })
    except Exception as e:
        logger.error(f"Failed to switch camera source: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.post("/debug/webcam")
async def debug_webcam_toggle(payload: PreviewToggleRequest) -> JSONResponse:
    """Enable/disable laptop webcam."""
    try:
        await webcam_service.set_active(payload.enabled)
        
        logger.info(f"📷 Webcam {'activated' if payload.enabled else 'deactivated'}")
        
        return JSONResponse({
            "status": "enabled" if payload.enabled else "disabled",
            "camera_source": "webcam"
        })
    except Exception as e:
        logger.error(f"Failed to toggle webcam: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.post("/debug/app-ready")
async def debug_app_ready(payload: dict[str, Any] | None = Body(default=None)) -> JSONResponse:
    """Local helper to simulate the mobile app signalling readiness with scenario control."""
    try:
        payload = payload or {}
        platform_id = payload.get("platform_id")
        
        # Scenario control parameters
        simulate_no_face = payload.get("simulate_no_face", False)
        simulate_lost_tracking = payload.get("simulate_lost_tracking", False)
        simulate_liveness_fail = payload.get("simulate_liveness_fail", False)
        
        # Store scenario params in session metadata
        if simulate_no_face:
            manager._current_session.metadata['simulate_no_face'] = True
        if simulate_lost_tracking:
            manager._current_session.metadata['simulate_lost_tracking'] = True
        if simulate_liveness_fail:
            manager._current_session.metadata['simulate_liveness_fail'] = True
        
        acknowledged = await manager.mark_app_ready(platform_id=platform_id)
        status = "acknowledged" if acknowledged else "ignored"
        return JSONResponse({
            "status": status,
            "scenario": {
                "no_face": simulate_no_face,
                "lost_tracking": simulate_lost_tracking,
                "liveness_fail": simulate_liveness_fail
            }
        })
    except Exception as e:
        logger.error(f"Failed to mark app ready: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.get("/preview")
async def preview_stream() -> StreamingResponse:
    """Stream preview from active camera source (realsense or webcam)."""
    boundary = "frame"

    async def frame_iterator() -> AsyncIterator[bytes]:
        try:
            # Route to appropriate camera source
            if active_camera_source == "webcam":
                source = webcam_service.preview_stream()
            else:
                source = manager.preview_frames()
            
            async for frame in source:
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
