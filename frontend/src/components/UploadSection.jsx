import { useEffect, useState } from "react";
import { API_ENDPOINTS } from "../config/api";

function UploadSection({ type }) {
  const isVideo = type === "video";
  const isImage = type === "image";
  const title = isVideo ? "Upload Video" : "Upload Image";
  const accept = isVideo ? "video/*" : "image/*";
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const onFileChange = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsLoading(true);
    setError("");
    setResult(null);

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(URL.createObjectURL(file));

    const body = new FormData();
    body.append("file", file);

    const endpoint = isVideo
      ? API_ENDPOINTS.videoUploadDetection
      : API_ENDPOINTS.imageUploadDetection;

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        body,
      });

      let data = null;
      try {
        data = await response.json();
      } catch {
        // Keep null for non-JSON server responses.
      }

      if (!response.ok) {
        throw new Error(data?.detail || "Upload detection failed");
      }

      setResult(data);
    } catch (uploadError) {
      setError(uploadError.message || "Upload detection failed");
    } finally {
      setIsLoading(false);
    }
  };

  const latestFrame =
    isVideo && result?.frame_detections?.length
      ? result.frame_detections[result.frame_detections.length - 1]
      : null;
  const personCount = isImage
    ? (result?.person_count ?? 0)
    : (latestFrame?.count ?? 0);
  const annotatedImageSrc =
    isImage && result?.annotated_jpeg_base64
      ? `data:image/jpeg;base64,${result.annotated_jpeg_base64}`
      : "";
  const processedVideoSrc =
    isVideo && result?.video_path
      ? `${API_ENDPOINTS.videoUploadDetectionDownload}?video_path=${encodeURIComponent(result.video_path)}`
      : "";

  return (
    <div className="upload-detection-layout">
      <div className="upload-layout">
        <h2>{title}</h2>
        <input type="file" accept={accept} onChange={onFileChange} />
        {isLoading && <p>Processing...</p>}
        {error && <p>{error}</p>}
        {previewUrl && isImage && (
          <img
            className="upload-preview"
            src={annotatedImageSrc || previewUrl}
            alt="Detected faces"
          />
        )}
        {previewUrl && isVideo && (
          <video
            className="upload-preview"
            src={processedVideoSrc || previewUrl}
            controls
          />
        )}
        {isVideo && processedVideoSrc && (
          <p>
            <a href={processedVideoSrc} target="_blank" rel="noreferrer">
              Download processed video
            </a>
          </p>
        )}
      </div>

      <div className="data-box">
        <h2>REALTIME DATA</h2>
        {isVideo ? (
          <>
            <p className="count-text">
              PERSON COUNT : <strong>{personCount}</strong>
            </p>
            {result && (
              <p>
                FRAMES PROCESSED : <strong>{result.frames_processed ?? 0}</strong>
              </p>
            )}
          </>
        ) : (
          <p className="count-text">
            PERSON COUNT : <strong>{personCount}</strong>
          </p>
        )}
        {isVideo && result?.frame_detections?.length > 0 && (
          <div className="frame-scroll-box">
            {result.frame_detections.map((frame) => (
              <p key={frame.frame}>
                Frame {frame.frame} : <strong>{frame.count}</strong>
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default UploadSection;
