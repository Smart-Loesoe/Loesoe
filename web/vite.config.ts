import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,          // luistert op 0.0.0.0 in Docker
    port: 5173,
    strictPort: true,
    hmr: {
      host: "localhost", // HMR via je host
      port: 5173,
      protocol: "ws",
    },
    watch: {
      usePolling: true,  // stabieler met Windows file sharing
      interval: 100,
    },
  },
  preview: {
    host: true,
    port: 5173,
    strictPort: true,
  },
});
