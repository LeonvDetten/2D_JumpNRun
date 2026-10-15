import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import { Level } from "../src/core/level";
import { BotEnv } from "../src/bot/env";
import { fixture, loadNet } from "./fixtures";

const hash = (a: Float32Array) => createHash("sha1").update(Buffer.from(a.buffer, a.byteOffset, a.byteLength)).digest("hex").slice(0, 16);

describe("bot observation and network match Python", () => {
  const net = loadNet();
  for (const run of fixture("bot.json").runs) {
    it(run.name, () => {
      const env = new BotEnv(Level.fromText(run.text, run.name), net.manifest.action_repeat);
      let obs = env.reset();
      let maxDiff = 0;
      run.steps.forEach((step: any, i: number) => {
        if (step.grid_full) expect(Array.from(obs.grid), `grid ${i}`).toEqual(step.grid_full);
        if (step.overview_full) expect(Array.from(obs.overview), `overview ${i}`).toEqual(step.overview_full);
        expect(hash(obs.grid), `grid hash at decision ${i}`).toBe(step.grid);
        expect(hash(obs.overview), `overview hash at decision ${i}`).toBe(step.overview);
        expect(Array.from(obs.vec), `vec at decision ${i}`).toEqual(step.vec);
        // Python stores torch's Categorical logits, i.e. log-probabilities: compare after log-softmax
        const logits = net.logits(obs);
        const max = Math.max(...logits);
        const lse = max + Math.log(logits.reduce((a, v) => a + Math.exp(v - max), 0));
        logits.forEach((v, k) => (maxDiff = Math.max(maxDiff, Math.abs(v - lse - step.logits[k]))));
        obs = env.step(step.action).obs;
      });
      expect(maxDiff).toBeLessThan(1e-4);
      expect(env.sim.status).toBe(run.status);
      expect(env.sim.frame).toBe(run.frame);
    });
  }
});
