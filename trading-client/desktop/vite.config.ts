import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// @ts-expect-error process is a nodejs global
const host = process.env.TAURI_DEV_HOST;

// https://vite.dev/config/
export default defineConfig(async () => ({
  plugins: [react(), tailwindcss()],

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1420,
    strictPort: true,
    host: "localhost",
    proxy: {
      "/api": {
        target: "http://76.13.180.80:8080",
        changeOrigin: true,
        ws: true,
      },
    },
    watch: {
      // 3. tell Vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
      // Windows: use polling for reliable file watching
      usePolling: true,
      interval: 500,
    },
  },

  // Build optimization — manual chunks for better caching
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // React core — rarely changes, cacheable
          "react-vendor": ["react", "react-dom"],
          // Icons — large library, separate chunk
          "icons": ["lucide-react"],
          // Charts — heavy dependency
          "charts": ["recharts"],
        },
      },
    },
    // Increase chunk size warning limit (Tauri apps can have larger chunks)
    chunkSizeWarningLimit: 600,
  },
}));
