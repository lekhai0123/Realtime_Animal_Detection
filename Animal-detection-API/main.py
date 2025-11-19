import cv2, numpy as np, time, uuid, json, threading, base64
from queue import Queue
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
import supervision as sv

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Load model
model = YOLO("models/best.pt")
model.fuse()
model.to("cuda")
dummy = np.zeros((640,640,3), np.uint8)
model(dummy)
LABELS = model.model.names if hasattr(model, "model") else model.names

# --- HÀM DECODE QUAN TRỌNG (Để đọc JPEG từ Android) ---
def decode_base64_image(data_str):
    try:
        if not data_str: return None
        # Xử lý header nếu có
        if "," in data_str:
            data_str = data_str.split(",")[1]
        
        # Decode base64 -> bytes
        img_data = base64.b64decode(data_str)
        # Convert bytes -> numpy array
        nparr = np.frombuffer(img_data, np.uint8)
        # Decode JPEG -> OpenCV Image (BGR)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print(f"Error decoding: {e}")
        return None

def to_sv_detections(result):
    det = sv.Detections.from_ultralytics(result)
    if getattr(det, "class_id", None) is None:
        det.class_id = result.boxes.cls.cpu().numpy().astype(int)
    return det

# --- GIỮ NGUYÊN LOGIC CŨ CỦA BẠN ---
def fix_rotation(frame, ori, angle):
    mode = "none"
    if ori == "portraitUp" and angle == 90:
        mode = "ROTATE_90_CLOCKWISE"
    elif ori == "portraitDown":
        mode = "ROTATE_90_COUNTERCLOCKWISE"
    elif ori == "landscapeLeft":
        mode = "ROTATE_180"
    
    # Bạn yêu cầu giữ nguyên: Trả về frame GỐC, không gọi cv2.rotate
    return frame, mode 

def infer_loop(frame_q: Queue, result_q: Queue):
    # Cấu hình Tracker
    tracker = sv.ByteTrack(track_activation_threshold=0.25)
    
    while True:
        item = frame_q.get()
        if item is None:
            break
        sid, frame, t_decode, t_rotate, t0 = item
        
        # Inference
        t_infer0 = time.time() * 1000
        # Lưu ý: Nếu ảnh từ Android JPEG to quá (vd 1920x1080), YOLO sẽ tự resize về 640x640
        res = model(frame, verbose=False, conf=0.4)[0]
        t_infer1 = time.time() * 1000
        
        # Tracking
        det_sv = to_sv_detections(res)
        tracked = tracker.update_with_detections(det_sv)
        
        h, w = frame.shape[:2]
        t_track = time.time() * 1000
        
        result_q.put((sid, tracked, w, h, t_decode, t_rotate, t_infer1 - t_infer0, t_track - t_infer1, t_track - t0))

@app.websocket("/ws/detect")
async def detect_ws(ws: WebSocket):
    await ws.accept()
    sid = str(uuid.uuid4())[:6]

    frame_q = Queue(maxsize=2)
    result_q = Queue(maxsize=2)

    thread = threading.Thread(target=infer_loop, args=(frame_q, result_q), daemon=True)
    thread.start()

    try:
        while True:
            try:
                msg = await ws.receive_text()
            except:
                break

            data = json.loads(msg)
            t0 = time.time() * 1000
            
            # 1. Decode JPEG từ Client gửi lên
            frame = decode_base64_image(data.get("image"))
            if frame is None:
                continue

            t_decode = time.time() * 1000 - t0

            # 2. Logic Rotation cũ (Tính toán mode nhưng không xoay ảnh)
            angle = int(data.get("angle", 0))
            ori = data.get("device_orientation", "portraitUp")
            
            frame, mode = fix_rotation(frame, ori, angle)
            
            t_rotate = time.time() * 1000 - t0 - t_decode

            # 3. Đẩy vào hàng đợi xử lý
            if frame_q.full():
                try: frame_q.get_nowait()
                except: pass

            frame_q.put((sid, frame, t_decode, t_rotate, t0))

            # 4. Nhận kết quả
            try:
                sid_r, tracked, w, h, td, tr, t_infer, t_track, t_total = result_q.get(timeout=4.0)
            except:
                continue

            t_backend_done = time.time() * 1000
            t_server_recv = t0 # Ước lượng time nhận

            dets = []
            for xyxy, cls_id, conf, tid in zip(
                tracked.xyxy, tracked.class_id, tracked.confidence, tracked.tracker_id
            ):
                x1, y1, x2, y2 = map(float, xyxy)
                dets.append({
                    "cls_name": LABELS[int(cls_id)],
                    "confidence": float(conf),
                    "bbox_xyxy": [x1, y1, x2, y2],
                    "track_id": int(tid) if tid else -1,
                })

            await ws.send_json({
                "detections": dets,
                "t_decode": td,
                "t_rotate": tr,
                "t_infer": t_infer,
                "t_track": t_track,
                "t_backend_total": t_total,
                "t_backend_done": t_backend_done,
                "t_server_recv": t_server_recv,
                "t_client_encode_done": data.get("t_client_encode_done", 0),
                "t_client_send_start": data.get("t_client_send_start", 0),
                "image_width": w,
                "image_height": h
            })

    except Exception as e:
        print(f"Socket error: {e}")
    finally:
        try: ws.close()
        except: pass
        frame_q.put(None)