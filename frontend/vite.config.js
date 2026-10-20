import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Tailwind v4 is wired as a Vite plugin rather than through a PostCSS config:
// the `@import "tailwindcss"` in src/index.css is all that is required, and
// there is no tailwind.config.js to keep in sync.
//
// The dev server runs on 5173, which is the origin the backend's CORS
// allowlist permits. If that port is changed here it must be changed in the
// backend's CORS_ORIGINS too, or browser requests will be blocked.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
  },
})
