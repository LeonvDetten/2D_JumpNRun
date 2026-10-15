import { describe, expect, it } from "vitest";
import { BOT_ACTIONS_V3, actionFromBits } from "../src/core/actions";
import { Level } from "../src/core/level";
import { Simulation, Status } from "../src/core/sim";
import { fixture } from "./fixtures";

const data = fixture("sim.json");

describe("simulation replays the stored bot solutions exactly", () => {
  for (const r of data.replays) {
    it(r.name, () => {
      const sim = new Simulation(Level.fromText(r.text));
      const trace: unknown[] = [];
      r.actions.forEach((a: number, i: number) => {
        if (sim.status !== Status.RUNNING) return;
        sim.step(BOT_ACTIONS_V3[a], 2);
        if (i % 25 === 0) trace.push(sim.stateSignature());
      });
      expect(trace).toEqual(r.trace);
      expect(sim.stateSignature()).toEqual(r.final);
      expect(sim.status).toBe(Status.WON);
      expect([sim.killsStomp, sim.killsShot]).toEqual(r.kills);
      expect(sim.jumps).toBe(r.jumps);
      expect(sim.maxX).toBe(r.max_x);
    });
  }
});

describe("simulation matches Python frame by frame for random inputs", () => {
  data.noise.forEach((n: any, idx: number) => {
    it(`noise run ${idx}`, () => {
      const sim = new Simulation(Level.fromText(n.text));
      const trace: unknown[] = [];
      n.codes.forEach((code: number, f: number) => {
        sim.step(actionFromBits(code));
        if (f % 10 === 0) trace.push(sim.stateSignature());
      });
      expect(trace).toEqual(n.trace);
      expect(sim.stateSignature()).toEqual(n.final);
    });
  });
});
