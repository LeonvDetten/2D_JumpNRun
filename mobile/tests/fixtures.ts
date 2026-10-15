import { readFileSync } from "node:fs";
import { join } from "node:path";
import { PolicyNet, type Manifest } from "../src/bot/net";

/** Load a golden JSON file written by tools/make_fixtures.py. */
export function fixture<T = any>(name: string): T {
  return JSON.parse(readFileSync(join(__dirname, "fixtures", name), "utf-8")) as T;
}

/** The exported bot network (public/bot). */
export function loadNet(): PolicyNet {
  const dir = join(__dirname, "..", "public", "bot");
  const manifest = JSON.parse(readFileSync(join(dir, "bot.json"), "utf-8")) as Manifest;
  const buf = readFileSync(join(dir, "weights.bin"));
  const weights = new Float32Array(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
  return new PolicyNet(manifest, weights);
}
