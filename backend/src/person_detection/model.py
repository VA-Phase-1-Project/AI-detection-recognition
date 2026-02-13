from ultralytics import YOLO
from .config import MODEL_OPENVINO_DIR, MODEL_PT_PATH


def load_model() -> YOLO:
    if MODEL_OPENVINO_DIR.exists():
        print("Loading OpenVINO model...")
        model = YOLO(str(MODEL_OPENVINO_DIR), task="detect")
    elif MODEL_PT_PATH.exists():
        print("Loading PyTorch model...")
        model = YOLO(str(MODEL_PT_PATH), task="detect")
    else:
        raise RuntimeError("No model found.")

    try:
        model.fuse()
    except Exception:
        pass

    return model


model = load_model()
