import { defineConfig } from "vitest/config";
import { VitePWA } from "vite-plugin-pwa";
import { readFileSync, writeFileSync } from "node:fs";
import type { Plugin } from "vite";

/**
 * Dev server only: POST a JPEG to /__screenshot?name=x and it is written to docs/medien/mobile_x.jpg
 * (screenshots for the documentation, taken from the running app).
 */
function screenshotEndpoint(): Plugin {
  return {
    name: "screenshot-endpoint",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/__screenshot", (req, res) => {
        const name = new URL(req.url ?? "", "http://x").searchParams.get("name")?.replace(/[^a-z0-9_]/g, "");
        if (req.method !== "POST" || !name) {
          res.statusCode = 400;
          return res.end();
        }
        const chunks: Buffer[] = [];
        req.on("data", (c: Buffer) => chunks.push(c));
        req.on("end", () => {
          writeFileSync(new URL(`../docs/medien/mobile_${name}.jpg`, import.meta.url), Buffer.concat(chunks));
          res.end("ok");
        });
      });
    },
  };
}

const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8"));
const version = `${pkg.version}+${new Date().toISOString().slice(0, 10)}`;

// Relative base: works on GitHub Pages (sub path) and inside a later Capacitor shell alike.
export default defineConfig({
  base: "./",
  define: { __APP_VERSION__: JSON.stringify(version) },
  build: { target: "es2022", assetsInlineLimit: 0 },
  worker: { format: "es" },
  plugins: [
    screenshotEndpoint(),
    VitePWA({
      registerType: "prompt",
      injectRegister: null, // registered by hand in src/platform/sw.ts (optional, the app runs without it)
      manifest: false, // public/manifest.webmanifest
      workbox: {
        globPatterns: ["**/*.{js,css,html,png,jpg,json,bin,webmanifest,svg}"],
        maximumFileSizeToCacheInBytes: 12 * 1024 * 1024,
      },
    }),
  ],
  test: {
    include: ["tests/**/*.test.ts", "tests-slow/**/*.test.ts"],
    exclude: process.env.SLOW ? [] : ["tests-slow/**"],
    testTimeout: 120_000,
  },
});
