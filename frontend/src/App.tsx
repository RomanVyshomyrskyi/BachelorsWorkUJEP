// App.tsx - simple status checker UI for the backend API

import { useEffect, useState } from "react";
// API_BASE should point to the backend API root (defined in ./lib/api)
import { API_BASE } from "./lib/api";

function App() {
  // msg holds the status text shown in the UI
  const [msg, setMsg] = useState("Checking API…");

  // On component mount, call the API health endpoint and update state
  useEffect(() => {
    fetch(`${API_BASE}/health`)
      // parse response as JSON
      .then((r) => r.json())
      // stringify and store the JSON response for display
      .then((j) => setMsg(JSON.stringify(j)))
      // if anything fails, show a friendly error message
      .catch((e) => setMsg("API not reachable: " + e.message));
  }, []); // empty deps => run once after first render

  // Render a small UI that shows the configured API_BASE and the last message
  return (
    <div style={{ fontFamily: "system-ui", padding: 24 }}>
      <h1>Vite + React + FastAPI</h1>
      <p>
        <strong>API_BASE:</strong> {API_BASE}
      </p>
      <pre>{msg}</pre>
    </div>
  );
}

export default App;
