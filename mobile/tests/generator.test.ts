import { describe, expect, it } from "vitest";
import { generate } from "../src/levelgen/generator";
import { levelKey } from "../src/core/levelkey";
import { fixture } from "./fixtures";

describe("level generator matches Python for the same (tier, seed)", () => {
  const levels = fixture("generator.json").levels;
  it(`${levels.length} generated levels`, () => {
    let mismatches = 0;
    for (const f of levels) {
      const level = generate(f.tier, f.seed, f.variant);
      const tag = `tier ${f.tier} seed ${f.seed} ${f.variant}`;
      if (level.toText() !== f.text) {
        mismatches++;
        if (mismatches < 4) expect(level.toText(), tag).toBe(f.text);
        continue;
      }
      expect(level.waypoints, tag).toEqual(f.waypoints);
      expect(level.needsPath, tag).toBe(f.needs_path);
      expect(level.buildingBlocks, tag).toEqual(f.blocks);
      expect(levelKey(level.toText()), tag).toBe(f.key);
    }
    expect(mismatches).toBe(0);
  });

  const keys = fixture("generator.json").keys as [number, number, string][];
  it(`${keys.length} more seeds (level keys only)`, () => {
    const wrong = keys.filter(([t, s, key]) => levelKey(generate(t, s).toText()) !== key);
    expect(wrong).toEqual([]);
  });
});
