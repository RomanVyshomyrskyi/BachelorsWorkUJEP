/**
 * @module vite-env
 * @description Vite environment type declarations.
 * Extends Vite's ImportMeta types to include custom environment variables.
 */

/// <reference types="vite/client" />

/**
 * Custom environment variables available at build time.
 *
 * @interface ImportMetaEnv
 * @property {string} VITE_BACKEND_URL - The base URL of the backend API server.
 *   Used by `api/service.ts` to determine where to send API requests.
 *
 * @example
 * // .env file
 * VITE_BACKEND_URL=http://localhost:8000
 *
 * @example
 * // Usage in code
 * const url = import.meta.env.VITE_BACKEND_URL;
 */
interface ImportMetaEnv {
  readonly VITE_BACKEND_URL: string;
}

/**
 * Extended ImportMeta interface with custom environment variables.
 *
 * @interface ImportMeta
 * @property {ImportMetaEnv} env - The environment variables object.
 */
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
