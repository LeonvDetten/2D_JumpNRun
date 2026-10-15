import { describe, expect, it } from "vitest";
import { Level } from "../src/core/level";
import { levelKey } from "../src/core/levelkey";
import { DistanceMap } from "../src/levelgen/distmap";
import { parFrames } from "../src/app/levelsIndex";
import { fixture } from "./fixtures";

describe("distance map matches Python", () => {
  for (const f of fixture("distmap.json").levels) {
    it(f.name, () => {
      const level = Level.fromText(f.text);
      const dm = new DistanceMap(level);
      const cells: number[][] = [];
      for (let c = 0; c < dm.cols; c++) {
        for (let r = 0; r < 13; r++) {
          const d = dm.distAt(c, r);
          if (d !== null) cells.push([c, r, Math.round(d * 1e9) / 1e9]);
        }
      }
      expect(cells.length).toBe(f.dist.length);
      cells.forEach((cell, i) => {
        expect(cell[0]).toBe(f.dist[i][0]);
        expect(cell[1]).toBe(f.dist[i][1]);
        expect(cell[2]).toBeCloseTo(f.dist[i][2], 7);
      });
      expect(dm.reachable).toBe(f.reachable);
      if (f.start === null) expect(dm.start).toBeNull();
      else expect(dm.start).toBeCloseTo(f.start, 9);
      expect(parFrames(level, null)).toBe(f.par);
      expect(levelKey(f.text)).toBe(f.key);
    });
  }
});
