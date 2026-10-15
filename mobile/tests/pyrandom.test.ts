import { describe, expect, it } from "vitest";
import { PyRandom, range, sha512 } from "../src/levelgen/pyrandom";
import { createHash } from "node:crypto";
import { fixture } from "./fixtures";

describe("PyRandom matches CPython's random.Random", () => {
  it("sha512 matches node:crypto", () => {
    for (const s of ["", "abc", "13:99", "x".repeat(300)]) {
      const ours = Buffer.from(sha512(new TextEncoder().encode(s))).toString("hex");
      expect(ours).toBe(createHash("sha512").update(s).digest("hex"));
    }
  });

  for (const c of fixture("pyrandom.json").cases) {
    it(`sequence for seed ${String(c.seed).slice(0, 12)}`, () => {
      const rng = new PyRandom(c.seed);
      let lastBit = 0;
      for (const op of c.ops) {
        switch (op[0]) {
          case "random": expect(rng.random()).toBe(op[1]); break;
          case "randint": expect(rng.randint(op[1], op[2])).toBe(op[3]); break;
          case "randrange": expect(rng.randrange(op[1], op[2])).toBe(op[3]); break;
          case "choice": expect(rng.choice(op[1])).toBe(op[2]); break;
          case "sample": expect(rng.sample(range(op[1][0], op[1][op[1].length - 1] + 1), op[2])).toEqual(op[3]); break;
          case "gamma": {
            // the platform libm's log is not always correctly rounded: allow the last bit (see docs/mobile.md)
            const v = rng.gammavariate(1.0, 1.0);
            if (v !== op[1]) lastBit++;
            expect(Math.abs(v - op[1])).toBeLessThanOrEqual(Math.abs(op[1]) * 2 ** -52);
            break;
          }
          case "choices": expect(rng.choiceWeighted(op[1], op[2])).toBe(op[3]); break;
          default: throw new Error(op[0]);
        }
      }
      expect(lastBit / c.ops.length).toBeLessThan(0.002);
    });
  }
});
