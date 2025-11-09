import os, time, cv2

def save_snapshot(frame, folder="snapshots"):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{int(time.time()*1000)}.jpg")
    cv2.imwrite(path, frame)
    return path
