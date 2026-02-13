from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent

# Model paths
MODEL_OPENVINO_DIR = BASE_DIR / "models" / "yolo26n_openvino_model"
MODEL_PT_PATH = BASE_DIR / "models" / "yolo26n.pt"

# Detection settings
CONF_THRESHOLD = 0.4
IOU_THRESHOLD = 0.5
FRAME_SIZE = (640, 360)
TRACKER_CONFIG = str(BASE_DIR / "bytetrack.yaml")

# RTSP (environment safe)
RTSP_USER = os.getenv("RTSP_USER", "admin")
RTSP_PASS = os.getenv("RTSP_PASS", "teamev108")
RTSP_IP = os.getenv("RTSP_IP", "172.18.10.108")

RTSP_URL = f"rtsp://{RTSP_USER}:{RTSP_PASS}@{RTSP_IP}:554/stream1"
