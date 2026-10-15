import { defineConfig } from "vitest/config";
import { VitePWA } from "vite-plugin-pwa";

// Relative base: works on GitHub Pages (sub path) and inside a later Capacitor shell alike.
export default defineConfig({
  base: "./",
  build: { target: "es2022", assetsInlineLimit: 0 },
  worker: { format: "es" },
  plugins: [
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: null, // registered by hand in src/platform/sw.ts (optional, the app runs without it)
      manifest: false, // public/manifest.webmanifest
      workbox: {
        globPatterns: ["**/*.{js,css,html,png,jpg,json,bin,webmanifest,svg}"],
        maximumFileSizeToCacheInBytes: 12 * 1024 * 1024,
      },
    }),
  ],
  test: {
    include: ["tests/**/*.test.ts"],
    testTimeout: 120_000,
  },
});
