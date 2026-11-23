import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    // Keep Vite's initial scan bounded and prebundle packages needing CJS interop.
    noDiscovery: true,
    include: [
      "cookie",
      "set-cookie-parser",
      "leaflet",
      "recharts",
      "react",
      "react-dom/client",
    ],
  },
  server: {
    preTransformRequests: false,
    // Keep local API calls same-origin so the HTTP-only auth cookie works
    // whether the app is opened on localhost or 127.0.0.1.
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
