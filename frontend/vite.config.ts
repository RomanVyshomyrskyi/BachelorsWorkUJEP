/**
 * @module vite.config
 * @description Vite configuration for the Superset Dashboard Manager frontend.
 * Configures React plugin, dev server, and API proxy rules.
 */

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Vite configuration for the React frontend application.
 *
 * Server settings:
 * - Host: 0.0.0.0 (accessible from network/Docker)
 * - Port: 3000
 * - Proxy: Routes API requests to backend at host.docker.internal:8000
 *
 * Proxy rules (all proxied to http://host.docker.internal:8000):
 * - /get_dashboard_expert_info - Export dashboard details
 * - /check_dashboard_import_ready - Validate import readiness
 * - /list_superset_servers - List configured servers
 * - /list_dashboards - List dashboards on a server
 * - /get_server_configs_json - Get server configs as JSON array
 * - /get_server_configs_full - Get full server configuration objects
 *
 * @example
 * // Start dev server
 * npm run dev
 *
 * @example
 * // Build for production
 * npm run build
 */
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/get_dashboard_expert_info': {
        target: 'http://host.docker.internal:8000',
        changeOrigin: true,
      },
      '/check_dashboard_import_ready': {
        target: 'http://host.docker.internal:8000',
        changeOrigin: true,
      },
      '/list_superset_servers': {
        target: 'http://host.docker.internal:8000',
        changeOrigin: true,
      },
      '/list_dashboards': {
        target: 'http://host.docker.internal:8000',
        changeOrigin: true,
      },
      '/get_server_configs_json': {
        target: 'http://host.docker.internal:8000',
        changeOrigin: true,
      },
      '/get_server_configs_full': {
        target: 'http://host.docker.internal:8000',
        changeOrigin: true,
      },
    }
  }
})
