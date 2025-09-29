
#!/usr/bin/env python3
# D435i RGB + IR live preview with robust restart on "processing block" and timeouts.

from __future__ import annotations
import sys, time, logging, argparse
import numpy as np

try:
    import pyrealsense2 as rs
    import cv2
except Exception as e:
    print(f"Import error: {e}", file=sys.stderr)
    sys.exit(1)

log = logging.getLogger("d435i_rgb_ir")

def build_cfg(width: int, height: int, fps: int, ir_index: int) -> rs.config:
    cfg = rs.config()
    cfg.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
    cfg.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
    # Prefer requested IR index; if not present we will fallback at runtime.
    cfg.enable_stream(rs.stream.infrared, ir_index, width, height, rs.format.y8, fps)
    return cfg

def start_pipeline(width: int, height: int, fps: int, ir_index: int):
    pipe = rs.pipeline()
    cfg = build_cfg(width, height, fps, ir_index)
    prof = pipe.start(cfg)
    dev = prof.get_device()
    name = dev.get_info(rs.camera_info.name)
    sn = dev.get_info(rs.camera_info.serial_number)
    log.info("Started on %s SN=%s", name, sn)
    return pipe, prof

def get_frames(pipe: rs.pipeline, timeout_ms: int):
    frames = pipe.wait_for_frames(timeout_ms=timeout_ms)
    color = frames.get_color_frame()
    # Try IR(1), IR(0), then first available IR
    ir = frames.get_infrared_frame(1) or frames.get_infrared_frame(0) or frames.first(rs.stream.infrared)
    return color, ir

def make_canvas(color_frame: rs.video_frame, ir_frame: rs.video_frame, flip_ir: bool, scale: float):
    c = np.asanyarray(color_frame.get_data())
    i = np.asanyarray(ir_frame.get_data())
    if flip_ir:
        i = np.fliplr(i)
    # Resize both with same scale
    if scale != 1.0:
        cw = int(c.shape[1] * scale); ch = int(c.shape[0] * scale)
        iw = int(i.shape[1] * scale); ih = int(i.shape[0] * scale)
        c = cv2.resize(c, (cw, ch), interpolation=cv2.INTER_AREA)
        i = cv2.resize(i, (iw, ih), interpolation=cv2.INTER_AREA)
    # IR is single-channel; convert to 3-channel for side-by-side
    i3 = cv2.cvtColor(i, cv2.COLOR_GRAY2BGR)
    h = min(c.shape[0], i3.shape[0])
    c = c[:h, :]; i3 = i3[:h, :]
    canvas = cv2.hconcat([c, i3])
    # Labels
    cv2.putText(canvas, "RGB", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,0), 2, cv2.LINE_AA)
    cv2.putText(canvas, "IR",  (c.shape[1] + 10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,255,255), 2, cv2.LINE_AA)
    return canvas

def run(width: int, height: int, fps: int, ir_index: int, timeout_ms: int, scale: float, flip_ir: bool):
    # Print device list first for clarity
    ctx = rs.context()
    if len(ctx.query_devices()) == 0:
        log.error("No RealSense device detected")
        sys.exit(2)

    # Main loop with auto-restart
    attempt = 0
    pipe = None
    prof = None
    try:
        while True:
            try:
                attempt += 1
                if pipe is None:
                    pipe, prof = start_pipeline(width, height, fps, ir_index)
                    attempt = 0  # reset after successful start

                while True:
                    try:
                        color, ir = get_frames(pipe, timeout_ms)
                    except RuntimeError as e:
                        msg = str(e).lower()
                        if "frame didn't arrive" in msg or "timeout" in msg:
                            log.warning("Timeout; continuing")
                            continue
                        if "processing block" in msg:
                            raise
                        # Unknown runtime error; bubble up
                        raise

                    if not color or not ir:
                        log.warning("Missing stream(s): color=%s ir=%s", bool(color), bool(ir))
                        continue

                    canvas = make_canvas(color, ir, flip_ir, scale)
                    cv2.imshow("D435i RGB | IR (press q/ESC to quit)", canvas)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (27, ord('q')):
                        return
            except RuntimeError as e:
                msg = str(e)
                log.error("RuntimeError: %s", msg)
                # Processing block or severe error: restart pipeline
                try:
                    if pipe is not None:
                        pipe.stop()
                except Exception:
                    pass
                pipe = None
                prof = None
                time.sleep(0.25)  # brief backoff before restart
                continue
    finally:
        try:
            if pipe is not None:
                pipe.stop()
        except Exception:
            pass
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

def parse():
    ap = argparse.ArgumentParser(description="Intel RealSense D435i RGB + IR Preview")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--ir-index", type=int, default=1, choices=[0,1], help="Prefer IR sensor index (D435i commonly 1)")
    ap.add_argument("--timeout-ms", type=int, default=1500)
    ap.add_argument("--scale", type=float, default=1.0, help="Resize factor for display")
    ap.add_argument("--flip-ir", action="store_true", help="Horizontally flip IR preview")
    ap.add_argument("--log", default="info", choices=["debug","info","warn","error"])
    return ap.parse_args()

if __name__ == "__main__":
    args = parse()
    lvl = dict(debug=logging.DEBUG, info=logging.INFO, warn=logging.WARNING, error=logging.ERROR)[args.log]
    logging.basicConfig(level=lvl, format="%(asctime)s | %(levelname)s | %(message)s")
    run(args.width, args.height, args.fps, args.ir_index, args.timeout_ms, args.scale, args.flip_ir)
