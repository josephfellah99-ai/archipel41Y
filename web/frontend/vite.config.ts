import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  base: "./",
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "icon-192.png", "icon-512.png"],
      manifest: {
        name: "Archipel41 – Agence d'architecture",
        short_name: "Archipel41",
        description: "Assistant numérique intelligent pour agences d'architecture",
        lang: "fr",
        start_url: "./",
        display: "standalone",
        background_color: "#F8F7F2",
        theme_color: "#253A33",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        navigateFallback: "index.html",
        navigateFallbackDenylist: [/^\/api\//],
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
        maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
        runtimeCaching: [],
      },
    }),
  ],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8041" } },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 1200 },
});
