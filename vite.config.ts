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
      ignored: ["**/.venv/**", "**/node_modules/**", "**/__pycache__/**"],
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    cssCodeSplit: true,
    cssMinify: true,
    sourcemap: false,
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes("node_modules/prismjs")) return "prism";
          if (id.includes("node_modules/react")) return "vendor-react";
        },
      },
    },
  },
});
