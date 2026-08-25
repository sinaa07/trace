import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/cases": "http://localhost:8000",
      "/evidence": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
