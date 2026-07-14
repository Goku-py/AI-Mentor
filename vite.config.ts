import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiTarget = process.env.VITE_PROXY_TARGET || "http://localhost:5000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api/v1": {
        target: apiTarget,
        changeOrigin: true,
      },
    },
    port: 5173,
    host: "localhost",
    watch: {
      ignored: ["**/.venv/**", "**/venv/**", "**/node_modules/**", "**/__pycache__/**"],
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
