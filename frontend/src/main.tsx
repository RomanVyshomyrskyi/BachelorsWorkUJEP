import React from "react";
import ReactDOM from "react-dom/client";
import Setup from "./pages/Setup";
import { API_BASE } from "./lib/api";

/**
 * Check whether the backend has been configured.
 * - Calls the /setup/status endpoint.
 * - Uses `cache: "no-store"` to avoid cached responses during app bootstrap.
 * - Returns `true` when the endpoint indicates `configured` is truthy.
 * - On any network or parse error, returns `false` (treat as not configured).
 */
async function isConfigured(): Promise<boolean> {
  try {
    const r = await fetch(`${API_BASE}/setup/status`, { cache: "no-store" });
    const j = await r.json();
    return !!j.configured;
  } catch {
    // If the request fails for any reason, assume not configured.
    return false;
  }
}

/**
 * Self-invoking async function used to:
 * - determine configuration status before rendering the app,
 * - dynamically import the main App only when needed (avoids loading app code when showing Setup),
 * - and render either the full App or the Setup page into the root element.
 */
(async () => {
  const configured = await isConfigured();

  // Non-null assertion: assume an element with id "root" exists in index.html.
  const root = document.getElementById("root")!;

  if (configured) {
    // Dynamically import the main App bundle only if the backend is configured.
    const App = (await import("./App")).default;
    ReactDOM.createRoot(root).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    );
  } else {
    // Render the Setup page when the backend is not configured.
    ReactDOM.createRoot(root).render(
      <React.StrictMode>
        <Setup />
      </React.StrictMode>
    );
  }
})();
