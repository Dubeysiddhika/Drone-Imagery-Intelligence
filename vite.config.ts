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
  },
});
