import supervision as sv

def create_tracker():
    # DeepSORT mặc định của Supervision
    return sv.ByteTrack()

def to_sv_detections(ultra_result):
    det = sv.Detections.from_ultralytics(ultra_result)
    if getattr(det, "class_id", None) is None:
        import numpy as np
        det.class_id = ultra_result.boxes.cls.cpu().numpy().astype(int)
    return det
