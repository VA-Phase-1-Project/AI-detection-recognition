const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const API_ENDPOINTS = {
  health: `${API_BASE}/health`,
  personDetectionStream: `${API_BASE}/api/person-detection/stream`,
  peopleCountWebRtcOffer: `${API_BASE}/api/people-count/webrtc/offer`,
  peopleCountCurrent: `${API_BASE}/api/people-count/current`,
  videoUploadDetection: `${API_BASE}/api/video-detection/upload`,
  videoUploadDetectionDownload: `${API_BASE}/api/video-detection/upload/download`,
  videoUploadDetectionStream: `${API_BASE}/api/video-detection/upload/stream`,
  imageUploadDetection: `${API_BASE}/api/image-detection/upload`,
  openvinoExport: `${API_BASE}/api/model/export/openvino`,
};
