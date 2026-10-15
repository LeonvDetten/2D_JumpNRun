// Port of jumpnrun/app/audio.py: chiptune effects and the music loop, synthesized at startup (no audio files).

type Wave = "square" | "triangle" | "saw" | "sine";

export class Synth {
  constructor(readonly rate: number) {}

  secs(s: number): number {
    return Math.trunc(this.rate * s);
  }

  env(n: number, attack = 0.005, release = 0.05): Float32Array {
    const out = new Float32Array(n);
    const a = Math.max(attack, 1e-4);
    const r = Math.max(release, 1e-4);
    for (let i = 0; i < n; i++) {
      const t = i / this.rate;
      out[i] = Math.min(1, Math.max(0, t / a)) * Math.min(1, Math.max(0, (n / this.rate - t) / r));
    }
    return out;
  }

  /** freq: a number or n frequencies (sweeps); the phase is accumulated so sweeps stay smooth. */
  osc(freq: number | Float32Array, n: number, wave: Wave = "square", duty = 0.5): Float32Array {
    const out = new Float32Array(n);
    let phase = 0;
    for (let i = 0; i < n; i++) {
      phase += (typeof freq === "number" ? freq : freq[i]) / this.rate;
      const frac = phase - Math.floor(phase);
      out[i] =
        wave === "square" ? (frac < duty ? 1 : -1)
        : wave === "triangle" ? 4 * Math.abs(frac - 0.5) - 1
        : wave === "saw" ? 2 * frac - 1
        : Math.sin(2 * Math.PI * phase);
    }
    return out;
  }

  noise(n: number, seed = 0): Float32Array {
    // small deterministic PRNG (mulberry32); the exact samples do not matter
    let s = (seed * 0x9e3779b9 + 0x6d2b79f5) >>> 0;
    const out = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      s = (s + 0x6d2b79f5) >>> 0;
      let t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      out[i] = (((t ^ (t >>> 14)) >>> 0) / 4294967296) * 2 - 1;
    }
    return out;
  }

  sweep(f0: number, f1: number, n: number): Float32Array {
    const out = new Float32Array(n);
    for (let i = 0; i < n; i++) out[i] = f0 * (f1 / f0) ** (n > 1 ? i / (n - 1) : 0);
    return out;
  }
}

const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
export function note(name: string): number {
  const pitch = name.slice(0, -1);
  const octave = parseInt(name.slice(-1), 10);
  return 440 * 2 ** ((NAMES.indexOf(pitch) + 12 * (octave - 4) - 9) / 12);
}

/** out = sum of k * product(arrays) (all arrays have the same length). */
function mix(k: number, ...arrays: Float32Array[]): Float32Array {
  const n = arrays[0].length;
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    let v = k;
    for (const a of arrays) v *= a[i];
    out[i] = v;
  }
  return out;
}

function add(target: Float32Array, start: number, src: Float32Array): void {
  const n = Math.min(src.length, target.length - start);
  for (let i = 0; i < n; i++) target[start + i] += src[i];
}

function sum(a: Float32Array, b: Float32Array): Float32Array {
  const out = new Float32Array(a.length);
  for (let i = 0; i < a.length; i++) out[i] = a[i] + b[i];
  return out;
}

function arpeggio(s: Synth, notes: string[], step: number, tail: number, wave: Wave = "square"): Float32Array {
  const total = s.secs(step * notes.length + tail);
  const out = new Float32Array(total);
  notes.forEach((name, i) => {
    const start = s.secs(step * i);
    const n = Math.min(s.secs(step + tail * 0.6), total - start);
    add(out, start, mix(0.22, s.osc(note(name), n, wave, 0.5), s.env(n, 0.003, tail * 0.5)));
  });
  return out;
}

/** name -> mono waveform in [-1, 1]. */
export function effects(rate: number): Record<string, Float32Array> {
  const s = new Synth(rate);
  const out: Record<string, Float32Array> = {};
  let n = s.secs(0.14);
  out.jump = mix(0.35, s.osc(s.sweep(260, 720, n), n, "square", 0.25), s.env(n, 0.003, 0.06));
  n = s.secs(0.16);
  out.shoot = mix(1, sum(mix(0.25, s.noise(n, 1)), mix(0.25, s.osc(s.sweep(1200, 180, n), n, "saw"))), s.env(n, 0.001, 0.12));
  n = s.secs(0.18);
  const decay = new Float32Array(n).map((_, i) => Math.exp(-i / 800));
  out.stomp = mix(1, sum(mix(0.6, s.osc(s.sweep(220, 50, n), n, "sine")), mix(0.2, s.noise(n, 2), decay)), s.env(n, 0.001, 0.1));
  n = s.secs(0.22);
  out.hit = mix(0.3, s.osc(s.sweep(900, 120, n), n, "square", 0.4), s.env(n, 0.001, 0.15));
  n = s.secs(0.6);
  out.death = mix(0.35, s.osc(s.sweep(500, 60, n), n, "triangle"), s.env(n, 0.005, 0.3));
  out.win = arpeggio(s, ["C5", "E5", "G5", "C6", "E6", "G6"], 0.09, 0.55);
  out.lose = arpeggio(s, ["G4", "D#4", "C4", "G3"], 0.16, 0.5, "triangle");
  n = s.secs(0.05);
  out.click = mix(0.3, s.osc(1400, n, "square", 0.3), s.env(n, 0.001, 0.04));
  n = s.secs(0.03);
  out.hover = mix(0.12, s.osc(2100, n, "sine"), s.env(n, 0.001, 0.025));
  n = s.secs(0.15);
  out.beep = mix(0.3, s.osc(660, n, "square", 0.5), s.env(n, 0.002, 0.08));
  n = s.secs(0.45);
  out.go = mix(0.32, s.osc(1320, n, "square", 0.5), s.env(n, 0.002, 0.3));
  n = s.secs(0.35);
  out.star = mix(0.25, sum(s.osc(note("E6"), n, "sine"), mix(0.5, s.osc(note("B6"), n, "sine"))), s.env(n, 0.002, 0.3));
  out.chest = arpeggio(s, ["G5", "C6", "E6"], 0.07, 0.4, "sine");
  return out;
}

/** A seamless loop: Am - F - C - G, twice; "menu" is slower and without drums. */
export function music(rate: number, kind: "game" | "menu"): Float32Array {
  const s = new Synth(rate);
  const bpm = kind === "game" ? 132 : 96;
  const beat = 60 / bpm;
  const chords: [string, string[]][] = [["A2", ["A4", "C5", "E5"]], ["F2", ["F4", "A4", "C5"]], ["C3", ["G4", "C5", "E5"]], ["G2", ["G4", "B4", "D5"]]];
  const bar = s.secs(beat * 4);
  const out = new Float32Array(bar * chords.length * 2);
  const eighth = s.secs(beat / 2);
  for (let rep = 0; rep < 2; rep++) {
    chords.forEach(([bass, arp], ci) => {
      const base = (rep * chords.length + ci) * bar;
      for (let b = 0; b < 8; b++) {
        const n = eighth;
        const f = note(bass) * (b % 4 === 3 ? 2 : 1);
        add(out, base + b * n, mix(0.16, s.osc(f, n, "triangle"), s.env(n, 0.004, 0.03)));
      }
      for (let k = 0; k < 16; k++) {
        const n = Math.floor(eighth / 2);
        const f = note(arp[(k + Math.floor(k / 4)) % 3]) * (kind === "menu" && k % 8 === 7 ? 2 : 1);
        add(out, base + k * n, mix(kind === "game" ? 0.05 : 0.06, s.osc(f, n, "square", 0.25), s.env(n, 0.002, 0.05)));
      }
      if (kind === "game") {
        for (let b = 0; b < 4; b++) {
          const n = s.secs(0.12);
          const k = base + b * s.secs(beat);
          add(out, k, mix(0.35, s.osc(s.sweep(150, 45, n), n, "sine"), s.env(n, 0.001, 0.08)));
          const h = k + s.secs(beat / 2);
          let m = s.secs(0.04);
          add(out, h, mix(0.05, s.noise(m, b), s.env(m, 0.001, 0.03)));
          if (b === 1 || b === 3) {
            m = s.secs(0.1);
            add(out, k, mix(0.12, s.noise(m, 10 + b), s.env(m, 0.001, 0.08)));
          }
        }
      }
    });
  }
  return out;
}
