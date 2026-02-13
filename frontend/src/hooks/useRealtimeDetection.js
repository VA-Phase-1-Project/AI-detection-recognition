import { useEffect, useRef, useState } from "react";
import { API_ENDPOINTS } from "../config/api";

export function useRealtimeDetection() {
  const [personCount, setPersonCount] = useState(0);
  const [backendReady, setBackendReady] = useState(false);
  const [useWebRtc, setUseWebRtc] = useState(false);
  const videoRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    let retryTimeout = null;

    const checkBackend = async () => {
      if (cancelled) return;

      try {
        const response = await fetch(API_ENDPOINTS.health);
        if (response.ok) {
          if (!cancelled) {
            setBackendReady(true);
          }
          return;
        }
      } catch {
        // Retry until backend is available.
      }

      retryTimeout = setTimeout(checkBackend, 1000);
    };

    checkBackend();

    return () => {
      cancelled = true;
      if (retryTimeout) {
        clearTimeout(retryTimeout);
      }
    };
  }, []);

  useEffect(() => {
    if (!backendReady) return;

    let cancelled = false;
    let peerConnection = null;
    let pollInterval = null;
    let pollingStarted = false;

    const applyPayload = (data) => {
      if (cancelled) return;
      setPersonCount(data.person_count ?? 0);
    };

    const startPolling = () => {
      if (pollingStarted) return;
      pollingStarted = true;

      const poll = async () => {
        try {
          const response = await fetch(API_ENDPOINTS.peopleCountCurrent);
          if (!response.ok) return;
          const data = await response.json();
          applyPayload(data);
        } catch {
          // Keep retrying in the existing interval.
        }
      };

      poll();
      pollInterval = setInterval(poll, 500);
    };

    const connectWebRtc = async () => {
      if (typeof RTCPeerConnection === "undefined") {
        startPolling();
        return;
      }

      try {
        peerConnection = new RTCPeerConnection();
        peerConnection.addTransceiver("video", { direction: "recvonly" });

        peerConnection.ontrack = (event) => {
          if (!videoRef.current) return;
          const [stream] = event.streams;
          if (stream) {
            videoRef.current.srcObject = stream;
            setUseWebRtc(true);
          }
        };

        const channel = peerConnection.createDataChannel("people-count");
        channel.onmessage = (event) => {
          try {
            applyPayload(JSON.parse(event.data));
          } catch {
            // Ignore malformed payloads.
          }
        };

        channel.onclose = () => {
          setUseWebRtc(false);
          startPolling();
        };

        const offer = await peerConnection.createOffer();
        await peerConnection.setLocalDescription(offer);

        const response = await fetch(API_ENDPOINTS.peopleCountWebRtcOffer, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sdp: offer.sdp,
            type: offer.type,
          }),
        });

        if (!response.ok) {
          throw new Error("WebRTC offer rejected");
        }

        const answer = await response.json();
        await peerConnection.setRemoteDescription(answer);
      } catch {
        setUseWebRtc(false);
        startPolling();
      }
    };

    connectWebRtc();

    return () => {
      cancelled = true;
      if (pollInterval) {
        clearInterval(pollInterval);
      }
      if (peerConnection) {
        peerConnection.close();
      }
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
    };
  }, [backendReady]);

  return { backendReady, personCount, useWebRtc, videoRef };
}
