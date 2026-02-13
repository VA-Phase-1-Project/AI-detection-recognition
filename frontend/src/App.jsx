import { useState } from "react";
import "./App.css";
import RealtimeSection from "./components/RealtimeSection";
import SectionTabs from "./components/SectionTabs";
import UploadSection from "./components/UploadSection";
import { useRealtimeDetection } from "./hooks/useRealtimeDetection";

function App() {
  const [activeSection, setActiveSection] = useState("upload-video");
  const { backendReady, personCount, useWebRtc, videoRef } = useRealtimeDetection();

  return (
    <div className="page">
      <h1 className="title">AI REALTIME DETECTION</h1>

      <SectionTabs activeSection={activeSection} onSelect={setActiveSection} />

      <div className="section-panel">
        {activeSection === "realtime" && (
          <RealtimeSection
            backendReady={backendReady}
            personCount={personCount}
            useWebRtc={useWebRtc}
            videoRef={videoRef}
          />
        )}

        {activeSection === "upload-video" && <UploadSection type="video" />}
        {activeSection === "upload-image" && <UploadSection type="image" />}
      </div>
    </div>
  );
}

export default App;
