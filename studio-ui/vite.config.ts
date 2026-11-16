import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8080',
      '/media': 'http://127.0.0.1:8080',
      '/tmp-media': 'http://127.0.0.1:8080',
      '/uploads': 'http://127.0.0.1:8080',
      '/music-bank': 'http://127.0.0.1:8080',
    },
  },
})
