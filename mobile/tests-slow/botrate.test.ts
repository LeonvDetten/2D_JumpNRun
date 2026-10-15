// Slow check (npm run test:bot): the TypeScript bot plays the exam level as well as the Python bot (98 %).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, it } from "vitest";
import { Level } from "../src/core/level";
import { Status } from "../src/core/sim";
import { BotEnv } from "../src/bot/env";
import { seededRandom } from "../src/bot/brain";
import { loadNet } from "../tests/fixtures";

const ROOT = join(__dirname, "..", "..");
const EPISODES = Number(process.env.BOT_EPISODES ?? 32);

it(`exam level, ${EPISODES} attempts at T = 0.3`, () => {
  const net = loadNet();
  const text = readFileSync(join(ROOT, "levels", "exam", "level.txt"), "utf-8");
  let wins = 0;
  const t0 = performance.now();
  let decisions = 0;
  for (let ep = 0; ep < EPISODES; ep++) {
    const env = new BotEnv(Level.fromText(text, "exam"), net.manifest.action_repeat);
    const random = seededRandom(1000 + ep);
    let obs = env.reset();
    for (;;) {
      const r = env.step(net.choose(obs, random));
      decisions++;
      obs = r.obs;
      if (r.terminated || r.truncated) break;
    }
    if (env.sim.status === Status.WON) wins++;
  }
  const ms = (performance.now() - t0) / decisions;
  console.log(`exam: ${wins}/${EPISODES} won, ${ms.toFixed(2)} ms per decision`);
  expect(wins / EPISODES).toBeGreaterThanOrEqual(0.9);
}, 1_800_000);
