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

@app.get("/")
def root():
    return {"status": "YOLO Realtime API running", "ws": "/ws/detect"}

@app.websocket("/ws/detect")
async def detect_ws(ws: WebSocket):
    await ws.accept()
    sid = str(uuid.uuid4())[:6]
    print(f"[{sid}] Connected")

    frame_q = Queue(maxsize=2)
    result_q = Queue(maxsize=2)

    thread = threading.Thread(
        target=infer_loop,
        args=(frame_q, result_q),
        daemon=True
    )
    thread.start()

    try:
        while True:
            # -----------------------------
            # 1) Nhận ảnh từ client
            # -----------------------------
            try:
                msg = await ws.receive_text()
            except:
                print(f"[{sid}] client closed")
                break

            data = json.loads(msg)
            t0 = time.time() * 1000

            frame = decode_base64_image(data.get("image"))
            if frame is None:
                print(f"[{sid}] decode error, continue")
                continue

            angle = int(data.get("angle", 0))
            ori = data.get("device_orientation", "portraitUp")
            t_decode = time.time() * 1000 - t0

            frame, mode = fix_rotation(frame, ori, angle)
            t_rotate = time.time() * 1000 - t0 - t_decode

            # drop frame cũ nếu hàng đợi đầy
            if frame_q.full():
                try:
                    frame_q.get_nowait()
                except:
                    pass

            frame_q.put((sid, frame, t_decode, t_rotate, t0))

            # -----------------------------
            # 2) Lấy kết quả infer
            # -----------------------------
            try:
                (
                    sid_r, tracked, decoded_w, decoded_h,
                    t_decode, t_rotate, t_infer, t_track, t_total
                ) = result_q.get(timeout=4.0)
            except:
                # KHÔNG đóng WebSocket
                print(f"[{sid}] infer timeout, continue")
                continue

            # -----------------------------
            # 3) Gửi kết quả về client
            # -----------------------------
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

            t_backend_done = time.time() * 1000

            await ws.send_json({
                "detections": dets,
                "fps": round(1000 / t_total, 2),
                "latency_ms": round(t_total, 2),
                "t_backend": round(t_total, 2),
                "t_backend_done": t_backend_done,
                "t_client_send": data.get("t_client_send", 0),
                "image_width": decoded_w,
                "image_height": decoded_h
            })

    except Exception as e:
        print(f"[{sid}] Error: {e}")

    # ❗ KHÔNG đóng WebSocket trong mỗi vòng lặp!
    finally:
        print(f"[{sid}] Disconnected")
        try:
            ws.close()
        except:
            pass
        frame_q.put(None)
