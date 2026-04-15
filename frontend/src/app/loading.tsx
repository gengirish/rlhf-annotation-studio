export default function Loading() {
  return (
    <div
      role="status"
      aria-label="Loading"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
      }}
    >
      <div style={{
        width: 36,
        height: 36,
        border: "3px solid #e5e7eb",
        borderTopColor: "#6366f1",
        borderRadius: "50%",
        animation: "spin 0.8s linear infinite",
      }} />
      <span className="sr-only">Loading content...</span>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
