import { API_ENDPOINTS } from "../config/api";

function RealtimeSection({
  backendReady,
  personCount,
  useWebRtc,
  videoRef,
}) {
  return (
    <div className="realtime-layout">
      <div className="video-box">
        {backendReady ? (
          useWebRtc ? (
            <video ref={videoRef} autoPlay playsInline muted className="video" />
          ) : (
            <img
              src={API_ENDPOINTS.personDetectionStream}
              alt="Live Stream"
              className="video"
            />
          )
        ) : (
          <div className="loading">Starting backend...</div>
        )}
      </div>

      <div className="data-box">
        <h2>REALTIME DATA</h2>
        <p className="count-text">
          PERSON COUNT : <strong>{personCount}</strong>
        </p>
      </div>
    </div>
  );
}

export default RealtimeSection;
