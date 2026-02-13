from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from person_detection.routes import router
from person_detection.webrtc import webrtc_manager

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "detector": "ultralytics-yolo (openvino if available)",
    }


@app.on_event("shutdown")
async def shutdown():
    await webrtc_manager.shutdown()
