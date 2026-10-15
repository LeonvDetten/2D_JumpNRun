// The bot's policy network (GridFeatures of jumpnrun/rl/policy.py + SB3 policy MLP), forward pass only.
//
//   grid (4,13,33) -> conv 4->32 (3x3, pad 1) -> conv 32->64 (s2) -> conv 64->64 (s2) -> flatten 2304 ┐
//   vec (23)       -> linear 23->64 -> relu                                                         ├ cat -> linear 2368->256 = pre
//   overview (4,13,40) -> conv 4->16 -> conv 16->32 (s2) -> flatten 4480 -> linear ->64 -> relu -> linear 64->256
//   features = relu(pre + overview head)  ->  linear 256->128 -> relu -> linear 128->7 = logits

import type { Observation } from "./env";

export interface Manifest {
  action_repeat: number;
  temperature: number;
  actions: number;
  grid: number[];
  vec: number[];
  overview: number[];
  floats: number;
  layers: Record<string, { offset: number; shape: number[] }>;
}

interface Conv {
  w: Float32Array;
  b: Float32Array;
  cin: number;
  cout: number;
  stride: number;
}

interface Linear {
  w: Float32Array; // (out, in)
  b: Float32Array;
  nin: number;
  nout: number;
}

function convOut(n: number, stride: number): number {
  return Math.floor((n + 2 - 3) / stride) + 1;
}

/** 3x3 convolution with padding 1 and ReLU, (C,H,W) layout as in PyTorch. */
function conv3x3(x: Float32Array, h: number, w: number, layer: Conv, relu: boolean): { y: Float32Array; h: number; w: number } {
  const { cin, cout, stride } = layer;
  const oh = convOut(h, stride);
  const ow = convOut(w, stride);
  const y = new Float32Array(cout * oh * ow);
  const W = layer.w;
  for (let co = 0; co < cout; co++) {
    const bias = layer.b[co];
    const outBase = co * oh * ow;
    for (let oy = 0; oy < oh; oy++) {
      for (let ox = 0; ox < ow; ox++) {
        let acc = bias;
        const iy0 = oy * stride - 1;
        const ix0 = ox * stride - 1;
        for (let ci = 0; ci < cin; ci++) {
          const wBase = (co * cin + ci) * 9;
          const inBase = ci * h * w;
          for (let ky = 0; ky < 3; ky++) {
            const iy = iy0 + ky;
            if (iy < 0 || iy >= h) continue;
            const row = inBase + iy * w;
            const wr = wBase + ky * 3;
            for (let kx = 0; kx < 3; kx++) {
              const ix = ix0 + kx;
              if (ix < 0 || ix >= w) continue;
              acc += W[wr + kx] * x[row + ix];
            }
          }
        }
        y[outBase + oy * ow + ox] = relu && acc < 0 ? 0 : acc;
      }
    }
  }
  return { y, h: oh, w: ow };
}

function linear(x: Float32Array, layer: Linear, relu: boolean, out?: Float32Array): Float32Array {
  const y = out ?? new Float32Array(layer.nout);
  const { w, b, nin, nout } = layer;
  for (let o = 0; o < nout; o++) {
    let acc = b[o];
    const base = o * nin;
    for (let i = 0; i < nin; i++) acc += w[base + i] * x[i];
    y[o] = relu && acc < 0 ? 0 : acc;
  }
  return y;
}

export class PolicyNet {
  private readonly c1: Conv;
  private readonly c2: Conv;
  private readonly c3: Conv;
  private readonly vecMlp: Linear;
  private readonly head: Linear;
  private readonly o1: Conv;
  private readonly o2: Conv;
  private readonly ovMlp: Linear;
  private readonly ovHead: Linear;
  private readonly pi: Linear;
  private readonly action: Linear;

  constructor(readonly manifest: Manifest, weights: Float32Array) {
    const get = (name: string) => {
      const l = manifest.layers[name];
      if (!l) throw new Error(`missing layer ${name}`);
      const size = l.shape.reduce((a, b) => a * b, 1);
      return { data: weights.subarray(l.offset, l.offset + size), shape: l.shape };
    };
    const conv = (name: string, stride: number): Conv => {
      const w = get(`${name}.weight`);
      return { w: w.data, b: get(`${name}.bias`).data, cout: w.shape[0], cin: w.shape[1], stride };
    };
    const lin = (name: string): Linear => {
      const w = get(`${name}.weight`);
      return { w: w.data, b: get(`${name}.bias`).data, nout: w.shape[0], nin: w.shape[1] };
    };
    const fe = "features_extractor";
    this.c1 = conv(`${fe}.cnn.0`, 1);
    this.c2 = conv(`${fe}.cnn.2`, 2);
    this.c3 = conv(`${fe}.cnn.4`, 2);
    this.vecMlp = lin(`${fe}.vec_mlp.0`);
    this.head = lin(`${fe}.head.0`);
    this.o1 = conv(`${fe}.ov_cnn.0`, 1);
    this.o2 = conv(`${fe}.ov_cnn.2`, 2);
    this.ovMlp = lin(`${fe}.ov_mlp.0`);
    this.ovHead = lin(`${fe}.ov_head`);
    this.pi = lin("mlp_extractor.policy_net.0");
    this.action = lin("action_net");
  }

  static async load(base = "./bot/"): Promise<PolicyNet> {
    const [manifest, buffer] = await Promise.all([
      fetch(base + "bot.json").then((r) => r.json() as Promise<Manifest>),
      fetch(base + "weights.bin").then((r) => r.arrayBuffer()),
    ]);
    const weights = new Float32Array(buffer);
    if (weights.length !== manifest.floats) throw new Error("bot weights are incomplete");
    return new PolicyNet(manifest, weights);
  }

  /** Action logits for one observation. */
  logits(obs: Observation): Float32Array {
    const [, gh, gw] = this.manifest.grid;
    let g = conv3x3(obs.grid, gh, gw, this.c1, true);
    g = conv3x3(g.y, g.h, g.w, this.c2, true);
    g = conv3x3(g.y, g.h, g.w, this.c3, true);
    const vec = linear(obs.vec, this.vecMlp, true);
    const cat = new Float32Array(g.y.length + vec.length);
    cat.set(g.y);
    cat.set(vec, g.y.length);
    const pre = linear(cat, this.head, false);
    const [, oh, ow] = this.manifest.overview;
    let o = conv3x3(obs.overview, oh, ow, this.o1, true);
    o = conv3x3(o.y, o.h, o.w, this.o2, true);
    const ov = linear(linear(o.y, this.ovMlp, true), this.ovHead, false);
    for (let i = 0; i < pre.length; i++) pre[i] = Math.max(0, pre[i] + ov[i]);
    return linear(linear(pre, this.pi, true), this.action, false);
  }

  /** Sharpened sampling: softmax(logits / T), as modelinfo.choose_actions with p^(1/T). */
  choose(obs: Observation, random: () => number, temperature = this.manifest.temperature): number {
    const logits = this.logits(obs);
    let max = -Infinity;
    for (const v of logits) max = Math.max(max, v);
    const p = Array.from(logits, (v) => Math.exp((v - max) / temperature));
    const total = p.reduce((a, b) => a + b, 0);
    let x = random() * total;
    for (let i = 0; i < p.length; i++) {
      x -= p[i];
      if (x < 0) return i;
    }
    return p.length - 1;
  }
}
