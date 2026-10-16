import { describe, expect, it } from "vitest";
import { Progress } from "../src/app/progress";

describe("progress", () => {
  it("a race win earns stars like a single run", () => {
    const p = new Progress();
    expect(p.recordRace("k", false, 600, 700).stars).toBe(0);
    expect(p.stars("k")).toBe(0);
    expect(p.recordRace("k", true, 700, 700).stars).toBe(3);
    p.recordRace("k", true, 1100, 700); // a slower win keeps the stars
    expect(p.stars("k")).toBe(3);
    expect(p.summary()).toEqual({ done: 1, stars: 3 });
    expect(p.bestFrames("k")).toBeNull(); // races do not set the single-player best time or ghost
  });
});
