import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000'
      // forwards `api` requests to `http://127.0.0.1:8000`, so CORS protection doesn't disable my code
      // CORS protection means "hey, if this request came from a different domain than the one we're on, that's SUS, so no blocking it"
    }
  }
})
