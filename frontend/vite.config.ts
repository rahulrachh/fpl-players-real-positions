import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Reads API_PROXY_TARGET from the environment (or a root-level .env file).
  const env = loadEnv(mode, '..', '')
  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': env.API_PROXY_TARGET || 'http://127.0.0.1:8000',
      },
    },
  }
})
