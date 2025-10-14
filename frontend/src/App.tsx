import { useEffect, useState } from "react";
import { API_BASE } from "./lib/api";

/**
 * App component — simple health-check UI for a backend API.
 *
 * This component:
 * - Maintains a piece of local state `msg` (initial value: "Checking API…")
 *   that holds the current status message returned from the API or an error message.
 * - On mount (empty dependency array) performs a side effect: it fetches the
 *   `${API_BASE}/health` endpoint, attempts to parse the response as JSON and
 *   stores the serialized result in `msg`. If the fetch or JSON parsing fails,
 *   `msg` is set to `API error: <error message>`.
 * - Renders a simple layout showing the configured `API_BASE` value and the
 *   current `msg` inside a <pre> block.
 *
 * Requirements / assumptions:
 * - A runtime/global constant `API_BASE` must be defined and accessible.
 *
 * Notes:
 * - The effect has no cleanup and runs only once after the component mounts.
 * - The fetched JSON is stringified with `JSON.stringify` before rendering.
 *
 * @returns JSX.Element — the rendered main UI with API base and health message.
 */
export default function App() {
  const [msg, setMsg] = useState("Checking API…");
  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((r) => r.json())
      .then((j) => setMsg(JSON.stringify(j)))
      .catch((e) => setMsg("API error: " + e.message));
  }, []);
  return (
    <main style={{ padding: 24, fontFamily: "system-ui" }}>
      <h1>App</h1>
      <p>
        <strong>API_BASE:</strong> {API_BASE}
      </p>
      <pre>{msg}</pre>
    </main>
  );
}
