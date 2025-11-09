import base64
import cv2
import numpy as np

def decode_base64_image(b64_string: str):
    try:
        # Nếu có tiền tố "data:image/..."
        if b64_string.startswith("data:image"):
            b64_string = b64_string.split(",")[1]

        img_data = base64.b64decode(b64_string)
        np_arr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # Nếu decode thất bại
        if frame is None or frame.size == 0:
            print("[WARN] decode_base64_image failed")
            return None

        return frame
    except Exception as e:
        print("[ERROR] decode_base64_image:", e)
        return None
