from __future__ import annotations

import cv2
import numpy as np
import time
from typing import Any, Callable, Iterator
from tempfile import NamedTemporaryFile
from pathlib import Path

from .config import (
    CONF_THRESHOLD,
    FRAME_SIZE,
    IOU_THRESHOLD,
    RTSP_URL,
    TRACKER_CONFIG,
)
from .model import model

CLASS_FILTER: list[int] | None = [0]
BBox = tuple[int, int, int, int]
Payload = dict[str, Any]


class FaceTracker:
    """Compatibility placeholder for legacy call signatures."""

    def __init__(self, max_distance: float = 80.0):
        self.max_distance = max_distance


# ==============================
# BOX/PAYLOAD HELPERS
# ==============================

def _extract_boxes_and_ids(
    result: Any,
) -> tuple[list[BBox], list[int] | None]:
    if result.boxes is None:
        return [], None

    boxes_raw = result.boxes.xyxy.cpu().numpy()
    boxes = [tuple(map(int, box)) for box in boxes_raw]

    if result.boxes.id is None:
        return boxes, None

    ids = result.boxes.id.cpu().numpy().astype(int).tolist()
    return boxes, ids


def _as_detection_payload(
    boxes: list[BBox],
    track_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    detections: list[dict[str, Any]] = []

    if track_ids is None:
        for idx, (x1, y1, x2, y2) in enumerate(boxes, start=1):
            detections.append({"id": idx, "bbox": [x1, y1, x2, y2]})
        return detections

    for (x1, y1, x2, y2), track_id in zip(boxes, track_ids):
        detections.append({"id": int(track_id), "bbox": [x1, y1, x2, y2]})
    return detections


def _annotate(
    frame: np.ndarray,
    boxes: list[BBox],
    track_ids: list[int] | None = None,
) -> np.ndarray:
    output = frame.copy()

    if track_ids is None:
        for idx, (x1, y1, x2, y2) in enumerate(boxes, start=1):
            cv2.rectangle(output, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                output,
                f"ID {idx}",
                (x1, max(20, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
    else:
        for (x1, y1, x2, y2), track_id in zip(boxes, track_ids):
            cv2.rectangle(output, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                output,
                f"ID {track_id}",
                (x1, max(20, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
    return output


def _count_detections(boxes: list[BBox], track_ids: list[int] | None) -> int:
    return len(set(track_ids)) if track_ids is not None else len(boxes)


def _empty_payload() -> Payload:
    return {
        "face_count": 0,
        "person_count": 0,
        "count": 0,
        "detections": [],
        "person_detections": [],
    }


def _make_payload(
    boxes: list[BBox],
    track_ids: list[int] | None,
) -> Payload:
    detections = _as_detection_payload(boxes, track_ids)
    count = _count_detections(boxes, track_ids)

    # Keep person fields for existing frontend/routes contract.
    return {
        "face_count": count,
        "person_count": count,
        "count": count,
        "detections": detections,
        "person_detections": detections,
    }


# ==============================
# INFERENCE MODES
# ==============================

def detect_frame_predict(
    frame: np.ndarray,
) -> tuple[dict[str, Any], np.ndarray]:
    result = model.predict(
        frame,
        conf=CONF_THRESHOLD,
        classes=CLASS_FILTER,
        verbose=False,
    )[0]
    boxes, _ = _extract_boxes_and_ids(result)
    payload = _make_payload(boxes, None)
    annotated = _annotate(frame, boxes, None)
    return payload, annotated


def detect_frame_track(
    frame: np.ndarray,
) -> tuple[dict[str, Any], np.ndarray]:
    result = model.track(
        frame,
        conf=CONF_THRESHOLD,
        iou=IOU_THRESHOLD,
        persist=True,
        tracker=TRACKER_CONFIG,
        classes=CLASS_FILTER,
        verbose=False,
    )[0]
    boxes, track_ids = _extract_boxes_and_ids(result)
    payload = _make_payload(boxes, track_ids)
    annotated = _annotate(frame, boxes, track_ids)
    return payload, annotated


def detect_frame(
    frame: np.ndarray,
    face_tracker: FaceTracker | None = None,
    person_tracker: FaceTracker | None = None,
) -> tuple[Payload, np.ndarray]:
    # Compatibility default: frame-level detection for single-image usage.
    _ = (face_tracker, person_tracker)
    return detect_frame_predict(frame)


# ==============================
# RTSP CAMERA
# ==============================

def open_realtime_capture(camera_index: int = 0):
    print("Trying RTSP:", RTSP_URL)
    rtsp_capture = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
    rtsp_capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if rtsp_capture.isOpened():
        return rtsp_capture

    rtsp_capture.release()
    webcam_capture = cv2.VideoCapture(camera_index)
    if webcam_capture.isOpened():
        print(f"RTSP unavailable, using local webcam (index {camera_index}).")
        return webcam_capture

    webcam_capture.release()
    return None


# ==============================
# MJPEG HELPER
# ==============================

def _multipart_frame(frame: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("Failed to encode frame")
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n\r\n"
        + buffer.tobytes()
        + b"\r\n"
    )


# ==============================
# REALTIME STREAM (TRACK)
# ==============================

def generate_realtime_detection_stream(
    camera_index: int = 0,
    on_frame: Callable[[dict[str, Any]], None] | None = None,
) -> Iterator[bytes]:
    capture = open_realtime_capture(camera_index)

    if capture is None:
        payload = _empty_payload()
        if on_frame:
            on_frame(payload)

        while True:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                frame,
                "Camera unavailable",
                (50, 240),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2,
            )
            yield _multipart_frame(frame)
            time.sleep(0.25)

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                capture.release()
                time.sleep(0.2)
                capture = open_realtime_capture(camera_index)
                if capture is None:
                    continue
                continue

            frame = cv2.resize(frame, FRAME_SIZE)
            payload, annotated = detect_frame_track(frame)

            if on_frame:
                on_frame(payload)

            yield _multipart_frame(annotated)
    finally:
        if capture is not None:
            capture.release()


# ==============================
# IMAGE UPLOAD (PREDICT)
# ==============================

def decode_uploaded_image(file_bytes: bytes) -> np.ndarray:
    data = np.frombuffer(file_bytes, dtype=np.uint8)
    frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Invalid image upload")
    return frame


def detect_faces_from_uploaded_image(file_bytes: bytes) -> Payload:
    frame = decode_uploaded_image(file_bytes)
    payload, annotated = detect_frame_predict(frame)

    ok, buffer = cv2.imencode(".jpg", annotated)
    if not ok:
        raise RuntimeError("Failed to encode frame")
    payload["annotated_jpeg"] = buffer.tobytes()

    return payload


# ==============================
# VIDEO UPLOAD SUMMARY (TRACK)
# ==============================

def analyze_uploaded_video(
    file_bytes: bytes,
    suffix: str = ".mp4",
) -> Payload:
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp.write(file_bytes)
        input_path = Path(temp.name)

    capture = cv2.VideoCapture(str(input_path))
    if not capture.isOpened():
        input_path.unlink(missing_ok=True)
        raise ValueError("Invalid video upload")

    output_path = input_path.with_name("processed_" + input_path.name)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = capture.get(cv2.CAP_PROP_FPS) or 25
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    writer = cv2.VideoWriter(
        str(output_path),
        fourcc,
        fps,
        (width, height),
    )

    unique_ids: set[int] = set()
    frames_processed = 0
    frame_counts: list[dict[str, int]] = []

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            frames_processed += 1

            frame = cv2.resize(frame, FRAME_SIZE)
            payload, annotated = detect_frame_track(frame)

            count = payload["count"]
            frame_counts.append(
                {
                    "frame": frames_processed,
                    "count": count,
                }
            )

            for detection in payload["detections"]:
                unique_ids.add(int(detection["id"]))

            annotated = cv2.resize(annotated, (width, height))
            writer.write(annotated)
    finally:
        capture.release()
        writer.release()
        input_path.unlink(missing_ok=True)

    return {
        "frames_processed": frames_processed,
        "unique_persons": len(unique_ids),
        "frame_wise_counts": frame_counts,
        "output_video_path": str(output_path),
    }


# ==============================
# VIDEO UPLOAD STREAM (TRACK)
# ==============================

def generate_uploaded_video_detection_stream(
    file_bytes: bytes,
    suffix: str = ".mp4",
    on_frame: Callable[[dict[str, Any]], None] | None = None,
) -> Iterator[bytes]:
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp.write(file_bytes)
        temp_path = Path(temp.name)

    capture = cv2.VideoCapture(str(temp_path))
    if not capture.isOpened():
        temp_path.unlink(missing_ok=True)
        raise ValueError("Invalid video upload")

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            frame = cv2.resize(frame, FRAME_SIZE)
            payload, annotated = detect_frame_track(frame)

            if on_frame:
                on_frame(payload)

            yield _multipart_frame(annotated)
    finally:
        capture.release()
        temp_path.unlink(missing_ok=True)
