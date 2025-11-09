import cv2, numpy as np, time, uuid, json, threading
from queue import Queue
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
from utils.image_tools import decode_base64_image
import supervision as sv

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

model = YOLO("models/best.pt")
model.fuse()
LABELS = model.model.names if hasattr(model, "model") else model.names

def to_sv_detections(result):
    det = sv.Detections.from_ultralytics(result)
    if getattr(det, "class_id", None) is None:
        det.class_id = result.boxes.cls.cpu().numpy().astype(int)
    return det

def fix_rotation(frame, ori, angle):
    mode = "none"
    if ori == "portraitUp" and angle == 90:
        mode = "ROTATE_90_CLOCKWISE"
    elif ori == "portraitDown":
        mode = "ROTATE_90_COUNTERCLOCKWISE"
    elif ori == "landscapeLeft":
        mode = "ROTATE_180"
    return frame, mode

def infer_loop(frame_q: Queue, result_q: Queue):
    tracker = sv.ByteTrack()
    while True:
        item = frame_q.get()
        if item is None:
            break
        sid, frame, t_decode, t_rotate, t0 = item
        t_infer0 = time.time() * 1000
        res = model(frame, verbose=False)[0]
        t_infer1 = time.time() * 1000
        det_sv = to_sv_detections(res)
        tracked = tracker.update_with_detections(det_sv)
        decoded_h, decoded_w = frame.shape[:2]
        t_track = time.time() * 1000
        result_q.put((sid, tracked, decoded_w, decoded_h,
                      t_decode, t_rotate, t_infer1 - t_infer0,
                      t_track - t_infer1, t_track - t0))

@app.websocket("/ws/detect")
async def detect_ws(ws: WebSocket):
    await ws.accept()
    sid = str(uuid.uuid4())[:6]
    print(f"[{sid}] Connected")

    frame_q, result_q = Queue(maxsize=2), Queue(maxsize=2)
    thread = threading.Thread(target=infer_loop, args=(frame_q, result_q), daemon=True)
    thread.start()

    try:
        while True:
            msg = await ws.receive_text()
            t0 = time.time() * 1000
            data = json.loads(msg)

            b64 = data.get("image")
            angle = int(data.get("angle", 0))
            ori = data.get("device_orientation", "portraitUp")

            frame = decode_base64_image(b64)
            if frame is None:
                continue
            t_decode = time.time() * 1000 - t0
            frame, mode = fix_rotation(frame, ori, angle)
            t_rotate = time.time() * 1000 - t0 - t_decode

            if frame_q.full():
                try: frame_q.get_nowait()
                except: pass
            frame_q.put((sid, frame, t_decode, t_rotate, t0))

            try:
                sid_r, tracked, decoded_w, decoded_h, t_decode, t_rotate, t_infer, t_track, t_total = result_q.get(timeout=2.0)
            except:
                continue

            dets = []
            for xyxy, cls_id, conf, tid in zip(
                tracked.xyxy,
                tracked.class_id,
                tracked.confidence,
                tracked.tracker_id
            ):
                x1, y1, x2, y2 = map(float, xyxy)
                dets.append({
                    "cls_name": LABELS[int(cls_id)],
                    "confidence": float(conf),
                    "bbox_xyxy": [x1, y1, x2, y2],
                    "track_id": int(tid) if tid is not None else None,
                })

            backend_t = t_total
            print(f"[{sid}] decode={t_decode:.1f}ms, rotate={t_rotate:.1f}ms, "
                  f"infer={t_infer:.1f}ms, track={t_track:.1f}ms, total={backend_t:.1f}ms")

            await ws.send_json({
                "detections": dets,
                "fps": round(1000 / backend_t, 2),
                "latency_ms": round(backend_t, 2),
                "t_backend": round(backend_t, 2),
                "class_stats": {},
                "image_width": decoded_w,
                "image_height": decoded_h,
            })

    except Exception as e:
        print(f"[{sid}] Error: {e}")
    finally:
        try:
            frame_q.put(None)
            if ws.client_state.name != "DISCONNECTED":
                await ws.close()
        except Exception:
            pass
        print(f"[{sid}] Disconnected")
