import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
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
      // The API proxy target is configurable for another machine/container.
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
    preview: {
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
