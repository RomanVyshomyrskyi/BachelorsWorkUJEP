import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

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
