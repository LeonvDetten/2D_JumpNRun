import { readFileSync } from "node:fs";
import { join } from "node:path";

/** Load a golden JSON file written by tools/make_fixtures.py. */
export function fixture<T = any>(name: string): T {
  return JSON.parse(readFileSync(join(__dirname, "fixtures", name), "utf-8")) as T;
}
