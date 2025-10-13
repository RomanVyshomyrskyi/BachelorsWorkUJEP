/**
 * Base URL used for API requests.
 *
 * Resolution order (first defined, non-empty wins):
 * 1. The global browser variable `window.__API_BASE__` (trimmed).
 * 2. The Vite environment variable `import.meta.env.VITE_API_URL`.
 * 3. The hard-coded fallback string `"/api"`.
 *
 * This value is determined at runtime in the browser. `window.__API_BASE__` is accessed via
 * `(window as any)` to allow injection of a global value before the app initializes; an empty
 * or whitespace-only string will be treated as not set because it is trimmed and then
 * falsy-check falls through to the next option.
 *
 * @constant
 * @type {string}
 * @remarks
 * Useful when the API endpoint differs between deployment environments or when embedding the
 * app in a host page that supplies a runtime API base.
 *
 * @example
 * // Provide at runtime from host page:
 * // <script>window.__API_BASE__ = "https://api.example.com";</script>
 *
 * @example
 * // Or set at build time via Vite:
 * // VITE_API_URL=https://api.example.com
 */
export const API_BASE = (window as any).__API_BASE__?.trim()
|| import.meta.env.VITE_API_URL
|| "/api";
