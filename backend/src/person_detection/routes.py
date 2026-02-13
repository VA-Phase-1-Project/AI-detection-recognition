from __future__ import annotations

import base64
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .detection import (
    analyze_uploaded_video,
    detect_faces_from_uploaded_image,
    generate_realtime_detection_stream,
    generate_uploaded_video_detection_stream,
)
from .shared_state import person_state
from .webrtc import AIORTC_AVAILABLE, webrtc_manager

router = APIRouter()


def _apply_state(payload: dict[str, object]) -> None:
    person_state["face_count"] = int(payload.get("face_count", 0))
    person_state["person_count"] = int(payload.get("person_count", 0))
    person_state["count"] = person_state["person_count"]
    person_state["detections"] = payload.get("detections", [])
    person_state["person_detections"] = payload.get("person_detections", [])


class RTCOffer(BaseModel):
    sdp: str
    type: str


@router.get("/api/person-detection/stream")
def person_detection_stream() -> StreamingResponse:
    return StreamingResponse(
        generate_realtime_detection_stream(on_frame=_apply_state),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/api/people-count/current")
def current_people_count() -> dict[str, object]:
    return {
        "count": person_state.get("count", 0),
        "face_count": person_state.get("face_count", 0),
        "person_count": person_state.get("person_count", 0),
        "detections": person_state.get("detections", []),
        "person_detections": person_state.get("person_detections", []),
    }


@router.post("/api/people-count/webrtc/offer")
async def people_count_webrtc_offer(offer: RTCOffer) -> dict[str, str]:
    if not AIORTC_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="WebRTC is unavailable because aiortc dependencies are missing",
        )

    try:
        return await webrtc_manager.create_answer(
            offer_sdp=offer.sdp,
            offer_type=offer.type,
            on_frame=_apply_state,
        )
    except RuntimeError as exc:
        status_code = 503 if "webcam" in str(exc).lower() else 500
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/api/image-detection/upload")
async def image_upload_detection(file: UploadFile = File(...)) -> dict[str, object]:
    try:
        file_bytes = await file.read()
        result = detect_faces_from_uploaded_image(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    encoded = base64.b64encode(result["annotated_jpeg"]).decode("ascii")
    result["annotated_jpeg_base64"] = encoded
    result.pop("annotated_jpeg", None)
    return result


@router.post("/api/model/export/openvino")
async def export_openvino_model(file: UploadFile = File(...)) -> dict[str, str]:
    from .openvino_export import OpenVINOExportError, export_onnx_to_openvino

    filename = file.filename or "model.onnx"
    suffix = Path(filename).suffix.lower()
    if suffix != ".onnx":
        raise HTTPException(status_code=400, detail="Only ONNX (.onnx) files are supported")

    try:
        file_bytes = await file.read()
        return export_onnx_to_openvino(
            onnx_bytes=file_bytes,
            model_name=Path(filename).stem or "model",
            output_root=Path("exports/openvino"),
        )
    except OpenVINOExportError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/video-detection/upload")
async def video_upload_detection(file: UploadFile = File(...)) -> dict[str, object]:
    suffix = Path(file.filename or "upload.mp4").suffix or ".mp4"

    try:
        file_bytes = await file.read()
        result = analyze_uploaded_video(file_bytes, suffix=suffix)
        return {
            "frames_processed": result["frames_processed"],
            "unique_person_count": result["unique_persons"],
            "frame_detections": result["frame_wise_counts"],
            "video_path": result["output_video_path"],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/video-detection/upload/download")
async def video_upload_detection_download(video_path: str) -> FileResponse:
    try:
        resolved_video_path = Path(video_path).expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Processed video not found") from exc

    tmp_dir = Path("/tmp").resolve()
    if tmp_dir not in resolved_video_path.parents:
        raise HTTPException(status_code=403, detail="Video path is not allowed")
    if not resolved_video_path.name.startswith("processed_"):
        raise HTTPException(status_code=400, detail="Invalid processed video path")

    return FileResponse(
        str(resolved_video_path),
        media_type="video/mp4",
        filename=resolved_video_path.name,
    )


@router.post("/api/video-detection/upload/stream")
async def video_upload_detection_stream(file: UploadFile = File(...)) -> StreamingResponse:
    suffix = Path(file.filename or "upload.mp4").suffix or ".mp4"

    try:
        file_bytes = await file.read()
        return StreamingResponse(
            generate_uploaded_video_detection_stream(
                file_bytes,
                suffix=suffix,
                on_frame=_apply_state,
            ),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
