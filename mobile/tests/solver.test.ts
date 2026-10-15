import { describe, expect, it } from "vitest";
import { BOT_ACTIONS_V3 } from "../src/core/actions";
import { Level } from "../src/core/level";
import { Simulation, Status } from "../src/core/sim";
import { LevelModel } from "../src/editor/model";
import { ProofKeeper, runSearch, type SearchMessage, type Searcher } from "../src/editor/proof";
import { generate } from "../src/levelgen/generator";
import { solve } from "../src/levelgen/solver";
import { fixture } from "./fixtures";

const replayWins = (level: Level, actions: number[]) => {
  const sim = new Simulation(level);
  for (const a of actions) sim.step(BOT_ACTIONS_V3[a], 2);
  return sim.status === Status.WON;
};

/** Runs the search synchronously (instead of a Web Worker). */
const inline = (): Searcher => ({
  start: (text, prefix, budget, on) => runSearch(text, prefix, budget, on),
  stop: () => undefined,
});

describe("solver and editor proof", () => {
  it("solves short generated levels; the way replays to a win", () => {
    for (const tier of [1, 3, 5]) {
      const level = generate(tier, 2);
      const r = solve(level, { maxExpansions: 60_000 });
      expect(r.solved, `tier ${tier}`).toBe(true);
      expect(replayWins(level, r.actions!)).toBe(true);
    }
  });

  it("proves hand-made levels like the desktop editor (legs + fallback)", () => {
    // the levels the Python editor proves with the base budget (serpentine and turm need "gründlicher prüfen")
    const names = ["test_serie/berg", "test_serie/parcours", "handmade8/zickzack"];
    const texts = fixture("sim.json").replays.filter((r: any) => names.includes(r.name));
    expect(texts.length).toBe(names.length);
    for (const r of texts) {
      let done: SearchMessage | null = null;
      runSearch(r.text, [], 120_000, (m) => {
        if (m[0] !== "leg") done = m;
      });
      expect(done![0], r.name).toBe("done");
      expect(done![1], r.name).toBe(true);
      expect(replayWins(Level.fromText(r.text), done![2] as number[])).toBe(true);
    }
  });

  it("keeps the proven way after an edit that does not touch it and cuts it otherwise", () => {
    const model = new LevelModel();
    const keeper = new ProofKeeper(model, inline);
    keeper.check();
    expect(keeper.state).toBe("complete");
    const full = keeper.proof.length;
    model.set(10, 0, "B"); // a block high in the sky
    keeper.revalidate();
    expect(keeper.state).toBe("complete");
    expect(keeper.proof.length).toBe(full);
    model.fill(12, 12, 13, 12, " "); // a pit on the way
    keeper.revalidate();
    expect(keeper.state).toBe("changed");
    expect(keeper.proof.length).toBeLessThan(full);
    keeper.check();
    expect(keeper.state).toBe("complete");
    model.undo();
    model.undo();
    keeper.revalidate();
    expect(["complete", "changed"]).toContain(keeper.state);
  });

  it("reports no chest as invalid", () => {
    const model = new LevelModel();
    const keeper = new ProofKeeper(model, inline);
    const [c, r] = model.find("C")[0];
    model.set(c, r, " ");
    keeper.revalidate();
    expect(keeper.state).toBe("invalid");
  });
});
