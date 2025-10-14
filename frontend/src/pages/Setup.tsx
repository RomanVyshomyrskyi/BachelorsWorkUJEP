import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";

/**
 * First-run setup page
 *
 * Allows testing a database DSN and initializing the application with
 * a site name and admin user. Uses the backend endpoints under `${API_BASE}/setup`.
 */
export default function Setup() {
    // form state
    const [dsn, setDsn] = useState("postgresql+psycopg://admin:admin@postgres:5432/app_db");
    const [site, setSite] = useState("My Site");
    const [email, setEmail] = useState("admin@example.com");
    const [pass, setPass] = useState("");

    // UI state
    const [status, setStatus] = useState<string | null>(null); // human readable status/messages
    const [testing, setTesting] = useState(false); // disables buttons during requests
    const [configured, setConfigured] = useState<boolean | null>(null); // null = loading

    // On mount, query backend to see if the app is already configured.
    // If the call fails, assume not configured.
    useEffect(() => {
        fetch(`${API_BASE}/setup/status`, { cache: "no-store" })
            .then(r => r.json()).then(j => setConfigured(j.configured))
            .catch(() => setConfigured(false));
    }, []);

    // Trigger a backend call to validate the provided DSN.
    // Updates `status` with the result. `testing` prevents repeated clicks.
    async function testDB() {
        setTesting(true);
        setStatus("Testing DB…");
        try {
            const r = await fetch(`${API_BASE}/setup/test-db`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ dsn })
            });
            const j = await r.json();
            setStatus(j.ok ? "DB OK!" : `DB Error ${j.error ?? ""}`);
        } finally {
            setTesting(false);
        }
    }

    // Initialize the application using the provided values.
    // On success, informs the user and reloads the page so the app can proceed.
    async function initialize() {
        setTesting(true);
        setStatus("Initializing…");
        try {
            const r = await fetch(`${API_BASE}/setup/initialize`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ dsn, site_name: site, admin_email: email, admin_password: pass })
            });
            if (!r.ok) {
                // read response text and throw to be caught below
                const t = await r.text();
                throw new Error(t);
            }
            setStatus("Setup complete Reloading…");
            setTimeout(() => window.location.reload(), 800);
        } catch (e: any) {
            setStatus(`Failed ${e.message ?? e}`);
        } finally {
            setTesting(false);
        }
    }

    // Loading state while we check configured status
    if (configured === null) return <p style={{padding:24}}>Loading…</p>;
    // If already configured, inform the user (no setup UI shown)
    if (configured) return <p style={{padding:24}}>Already configured. Reload if you just finished.</p>;

    // Setup form UI
    return (
        <main style={{ maxWidth: 640, margin: "2rem auto", fontFamily: "system-ui" }}>
            <h1>First-run Setup</h1>

            <label>DB DSN</label>
            <input value={dsn} onChange={e=>setDsn(e.target.value)} style={{width:"100%",margin:"6px 0 14px"}} />

            <label>Site name</label>
            <input value={site} onChange={e=>setSite(e.target.value)} style={{width:"100%",margin:"6px 0 14px"}} />

            <label>Admin email</label>
            <input value={email} onChange={e=>setEmail(e.target.value)} style={{width:"100%",margin:"6px 0 14px"}} />

            <label>Admin password</label>
            <input type="password" value={pass} onChange={e=>setPass(e.target.value)} style={{width:"100%",margin:"6px 0 14px"}} />

            <div style={{display:"flex",gap:8,marginTop:6}}>
                {/* disable actions while a request is in flight; require a password to initialize */}
                <button onClick={testDB} disabled={testing}>Test DB</button>
                <button onClick={initialize} disabled={testing || !pass}>Initialize</button>
            </div>

            {/* status messages shown below the buttons */}
            {status && <p style={{marginTop:12}}>{status}</p>}
            <p style={{marginTop:16,opacity:.7}}><code>API_BASE: {API_BASE}</code></p>
        </main>
    );
}
