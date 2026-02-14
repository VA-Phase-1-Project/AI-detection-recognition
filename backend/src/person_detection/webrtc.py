from __future__ import annotations

import cv2
from fractions import Fraction
from typing import Any, Callable
import asyncio
import json

from .detection import detect_frame_track
from .config import FRAME_SIZE
from .detection import open_realtime_capture

try:
    from aiortc import RTCPeerConnection, RTCSessionDescription
    from aiortc.mediastreams import MediaStreamError, MediaStreamTrack
    from av import VideoFrame

    AIORTC_AVAILABLE = True
except Exception:
    RTCPeerConnection = Any 
    RTCSessionDescription = Any
    MediaStreamTrack = object  
    MediaStreamError = RuntimeError
    VideoFrame = Any 
    AIORTC_AVAILABLE = False


class DetectionVideoTrack(MediaStreamTrack):
    kind = "video"

    def __init__(
        self,
        on_frame: Callable[[dict[str, Any]], None],
        camera_index: int = 0,
        fps: int = 24,
    ) -> None:
        super().__init__()
        self._on_frame = on_frame
        self._fps = max(1, fps)
        self._pts = 0
        self._capture = open_realtime_capture()

        if self._capture is None:
            raise RuntimeError("Could not open webcam")

    async def recv(self) -> VideoFrame:
        ok, frame = self._capture.read()
        if not ok:
            raise MediaStreamError

        frame = cv2.resize(frame, FRAME_SIZE)
        payload, annotated = detect_frame_track(frame)
        self._on_frame(payload)

        video_frame = VideoFrame.from_ndarray(annotated, format="bgr24")
        video_frame.pts = self._pts
        video_frame.time_base = Fraction(1, self._fps)
        self._pts += 1

        await asyncio.sleep(1 / self._fps)
        return video_frame

    def stop(self) -> None:
        if self._capture is not None and self._capture.isOpened():
            self._capture.release()
        super().stop()


class WebRTCSessionManager:
    def __init__(self) -> None:
        self._pcs: set[Any] = set()

    async def create_answer(
        self,
        offer_sdp: str,
        offer_type: str,
        on_frame: Callable[[dict[str, Any]], None],
    ) -> dict[str, str]:
        if not AIORTC_AVAILABLE:
            raise RuntimeError("aiortc is not installed")

        pc = RTCPeerConnection()
        self._pcs.add(pc)
        data_channel: Any = None

        @pc.on("datachannel")
        def on_datachannel(channel: Any) -> None:
            nonlocal data_channel
            data_channel = channel

        def push_payload(payload: dict[str, Any]) -> None:
            on_frame(payload)
            if data_channel is not None and data_channel.readyState == "open":
                data_channel.send(
                    json.dumps(
                        {
                            "person_count": int(payload.get("person_count", 0)),
                            "face_count": int(payload.get("face_count", 0)),
                            "detections": payload.get("detections", []),
                            "person_detections": payload.get("person_detections", []),
                        }
                    )
                )

        track = DetectionVideoTrack(on_frame=push_payload)
        pc.addTrack(track)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            if pc.connectionState in {"failed", "closed", "disconnected"}:
                await pc.close()
                self._pcs.discard(pc)

        await pc.setRemoteDescription(
            RTCSessionDescription(sdp=offer_sdp, type=offer_type)
        )
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        local = pc.localDescription
        return {
            "sdp": local.sdp,
            "type": local.type,
        }

    async def shutdown(self) -> None:
        pcs = list(self._pcs)
        for pc in pcs:
            await pc.close()
            self._pcs.discard(pc)


webrtc_manager = WebRTCSessionManager()
