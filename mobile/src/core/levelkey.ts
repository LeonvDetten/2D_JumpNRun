// level_key of jumpnrun/app/progress.py: first 16 hex chars of the SHA-1 of the normalised level text.
// Same key as on the desktop, so an exported save.json matches levels on both sides.

import { rstrip } from "./level";

export function levelKey(text: string): string {
  const rows = text.replace(/\r\n/g, "\n").split("\n").map(rstrip);
  while (rows.length && !rows[rows.length - 1]) rows.pop();
  return sha1Hex(new TextEncoder().encode(rows.join("\n"))).slice(0, 16);
}

export function sha1Hex(msg: Uint8Array): string {
  const len = msg.length;
  const padLen = ((len + 8) >> 6) * 64 + 64;
  const data = new Uint8Array(padLen);
  data.set(msg);
  data[len] = 0x80;
  const view = new DataView(data.buffer);
  view.setUint32(padLen - 8, Math.floor((len * 8) / 0x100000000));
  view.setUint32(padLen - 4, (len * 8) >>> 0);
  let h0 = 0x67452301;
  let h1 = 0xefcdab89;
  let h2 = 0x98badcfe;
  let h3 = 0x10325476;
  let h4 = 0xc3d2e1f0;
  const w = new Uint32Array(80);
  for (let off = 0; off < padLen; off += 64) {
    for (let t = 0; t < 16; t++) w[t] = view.getUint32(off + t * 4);
    for (let t = 16; t < 80; t++) {
      const x = w[t - 3] ^ w[t - 8] ^ w[t - 14] ^ w[t - 16];
      w[t] = (x << 1) | (x >>> 31);
    }
    let a = h0;
    let b = h1;
    let c = h2;
    let d = h3;
    let e = h4;
    for (let t = 0; t < 80; t++) {
      let f: number;
      let k: number;
      if (t < 20) {
        f = (b & c) | (~b & d);
        k = 0x5a827999;
      } else if (t < 40) {
        f = b ^ c ^ d;
        k = 0x6ed9eba1;
      } else if (t < 60) {
        f = (b & c) | (b & d) | (c & d);
        k = 0x8f1bbcdc;
      } else {
        f = b ^ c ^ d;
        k = 0xca62c1d6;
      }
      const temp = (((a << 5) | (a >>> 27)) + f + e + k + w[t]) >>> 0;
      e = d;
      d = c;
      c = (b << 30) | (b >>> 2);
      b = a;
      a = temp;
    }
    h0 = (h0 + a) >>> 0;
    h1 = (h1 + b) >>> 0;
    h2 = (h2 + c) >>> 0;
    h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0;
  }
  return [h0, h1, h2, h3, h4].map((h) => (h >>> 0).toString(16).padStart(8, "0")).join("");
}
