const TABS = [
  { id: "realtime", label: "Realtime Video" },
  { id: "upload-video", label: "Upload Video" },
  { id: "upload-image", label: "Upload Image" },
];

function SectionTabs({ activeSection, onSelect }) {
  return (
    <div className="tabs">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={`tab ${activeSection === tab.id ? "active" : ""}`}
          onClick={() => onSelect(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export default SectionTabs;
