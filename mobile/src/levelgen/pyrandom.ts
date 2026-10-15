// Bit-exact port of CPython's random.Random (MT19937) for the calls the level generator makes.
// Same (tier, seed) string seed -> the same random levels as on the desktop. Parity: tests/pyrandom.test.ts.

const N = 624;
const M = 397;

export class PyRandom {
  private mt = new Uint32Array(N);
  private mti = N + 1;

  constructor(seed: string | number) {
    this.seed(seed);
  }

  /** random.seed(a) with version 2: str -> int.from_bytes(a + sha512(a)), int -> abs(a). */
  seed(a: string | number): void {
    let bytes: Uint8Array;
    if (typeof a === "string") {
      const enc = new TextEncoder().encode(a);
      const digest = sha512(enc);
      bytes = new Uint8Array(enc.length + digest.length);
      bytes.set(enc);
      bytes.set(digest, enc.length);
    } else {
      let n = BigInt(Math.abs(Math.trunc(a)));
      const out: number[] = [];
      while (n > 0n) {
        out.unshift(Number(n & 0xffn));
        n >>= 8n;
      }
      bytes = new Uint8Array(out);
    }
    // big-endian bytes -> little-endian 32-bit words of the integer (CPython random_seed)
    let first = 0;
    while (first < bytes.length && bytes[first] === 0) first++;
    const sig = bytes.subarray(first);
    const words = Math.max(1, Math.ceil(sig.length / 4));
    const key = new Uint32Array(words);
    for (let i = 0; i < sig.length; i++) {
      const fromEnd = sig.length - 1 - i; // byte significance
      key[fromEnd >> 2] |= sig[i] << (8 * (fromEnd & 3));
    }
    this.initByArray(key);
  }

  private initGenrand(s: number): void {
    const mt = this.mt;
    mt[0] = s >>> 0;
    for (let i = 1; i < N; i++) {
      const prev = mt[i - 1] ^ (mt[i - 1] >>> 30);
      mt[i] = (Math.imul(1812433253, prev) + i) >>> 0;
    }
    this.mti = N;
  }

  private initByArray(key: Uint32Array): void {
    const mt = this.mt;
    this.initGenrand(19650218);
    let i = 1;
    let j = 0;
    const len = key.length;
    for (let k = N > len ? N : len; k; k--) {
      const prev = mt[i - 1] ^ (mt[i - 1] >>> 30);
      mt[i] = ((mt[i] ^ Math.imul(prev, 1664525)) + key[j] + j) >>> 0;
      i++;
      j++;
      if (i >= N) {
        mt[0] = mt[N - 1];
        i = 1;
      }
      if (j >= len) j = 0;
    }
    for (let k = N - 1; k; k--) {
      const prev = mt[i - 1] ^ (mt[i - 1] >>> 30);
      mt[i] = ((mt[i] ^ Math.imul(prev, 1566083941)) - i) >>> 0;
      i++;
      if (i >= N) {
        mt[0] = mt[N - 1];
        i = 1;
      }
    }
    mt[0] = 0x80000000;
  }

  private genrandUint32(): number {
    const mt = this.mt;
    if (this.mti >= N) {
      let kk = 0;
      for (; kk < N - M; kk++) {
        const y = (mt[kk] & 0x80000000) | (mt[kk + 1] & 0x7fffffff);
        mt[kk] = mt[kk + M] ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0);
      }
      for (; kk < N - 1; kk++) {
        const y = (mt[kk] & 0x80000000) | (mt[kk + 1] & 0x7fffffff);
        mt[kk] = mt[kk + (M - N)] ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0);
      }
      const y = (mt[N - 1] & 0x80000000) | (mt[0] & 0x7fffffff);
      mt[N - 1] = mt[M - 1] ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0);
      this.mti = 0;
    }
    let y = mt[this.mti++];
    y ^= y >>> 11;
    y ^= (y << 7) & 0x9d2c5680;
    y ^= (y << 15) & 0xefc60000;
    y ^= y >>> 18;
    return y >>> 0;
  }

  /** random(): float in [0, 1) with 53 random bits. */
  random(): number {
    const a = this.genrandUint32() >>> 5;
    const b = this.genrandUint32() >>> 6;
    return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0);
  }

  /** getrandbits(k) for 0 <= k <= 32. */
  getrandbits(k: number): number {
    if (k <= 0) return 0;
    if (k > 32) throw new Error("getrandbits > 32 not needed here");
    return this.genrandUint32() >>> (32 - k);
  }

  private randbelow(n: number): number {
    if (n <= 0) return 0;
    const k = 32 - Math.clz32(n); // n.bit_length()
    let r = this.getrandbits(k);
    while (r >= n) r = this.getrandbits(k);
    return r;
  }

  randrange(start: number, stop?: number): number {
    if (stop === undefined) {
      if (start > 0) return this.randbelow(start);
      throw new Error("empty range for randrange()");
    }
    const width = stop - start;
    if (width > 0) return start + this.randbelow(width);
    throw new Error(`empty range for randrange(${start}, ${stop})`);
  }

  randint(a: number, b: number): number {
    return this.randrange(a, b + 1);
  }

  choice<T>(seq: readonly T[]): T {
    if (!seq.length) throw new Error("Cannot choose from an empty sequence");
    return seq[this.randbelow(seq.length)];
  }

  /** choices(population, weights)[0] (k=1). */
  choiceWeighted<T>(population: readonly T[], weights: readonly number[]): T {
    const cum: number[] = [];
    let acc = 0;
    for (const w of weights) {
      acc += w;
      cum.push(acc);
    }
    const total = cum[cum.length - 1] + 0.0;
    if (!(total > 0)) throw new Error("Total of weights must be greater than zero");
    const x = this.random() * total;
    // bisect_right(cum, x, 0, hi=n-1)
    let lo = 0;
    let hi = population.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (x < cum[mid]) hi = mid;
      else lo = mid + 1;
    }
    return population[lo];
  }

  /** sample(population, k) with CPython's pool / set strategy. */
  sample<T>(population: readonly T[], k: number): T[] {
    const n = population.length;
    if (k < 0 || k > n) throw new Error("Sample larger than population or is negative");
    const result: T[] = new Array(k);
    let setsize = 21;
    if (k > 5) setsize += 4 ** Math.ceil(Math.log(k * 3) / Math.log(4));
    if (n <= setsize) {
      const pool = population.slice();
      for (let i = 0; i < k; i++) {
        const j = this.randbelow(n - i);
        result[i] = pool[j];
        pool[j] = pool[n - i - 1];
      }
    } else {
      const selected = new Set<number>();
      for (let i = 0; i < k; i++) {
        let j = this.randbelow(n);
        while (selected.has(j)) j = this.randbelow(n);
        selected.add(j);
        result[i] = population[j];
      }
    }
    return result;
  }

  /** gammavariate(alpha, beta); the generator only uses alpha == 1 (an exponential draw). */
  gammavariate(alpha: number, beta: number): number {
    if (alpha !== 1.0) throw new Error("only alpha == 1 is ported");
    return -logCorrectlyRounded(1.0 - this.random()) * beta;
  }
}

// ------------------------------------------------------------------------- correctly rounded log
// JS engines' Math.log may differ from the C library in the last bit; that would change level styles.
// CPython uses the platform libm, whose log is correctly rounded in practice, so we compute ln(x) with
// 200-bit fixed point arithmetic and round once.
const P = 200n;
const ONE = 1n << P;
const F64 = new Float64Array(1);
const U64 = new BigUint64Array(F64.buffer);

function atanhSeries(zSigned: bigint): bigint {
  // atanh(z) = z + z^3/3 + z^5/5 + ... (z in fixed point, |z| <= 1/3); odd, so work on |z|
  // (a right shift of a negative BigInt never reaches 0)
  if (zSigned < 0n) return -atanhSeries(-zSigned);
  const z = zSigned;
  const z2 = (z * z) >> P;
  let term = z;
  let sum = 0n;
  for (let k = 1n; term !== 0n; k += 2n) {
    sum += term / k;
    term = (term * z2) >> P;
  }
  return sum;
}
const LN2 = 2n * atanhSeries(ONE / 3n);
const SQRT2_FP = BigInt(Math.round(Math.SQRT2 * 2 ** 52)) << (P - 52n);

export function logCorrectlyRounded(x: number): number {
  if (!(x > 0) || !Number.isFinite(x)) return Math.log(x);
  if (x === 1) return 0;
  F64[0] = x;
  const bits = U64[0];
  let exp = Number((bits >> 52n) & 0x7ffn);
  let mant = bits & ((1n << 52n) - 1n);
  if (exp === 0) {
    // subnormal: normalise
    while (!(mant & (1n << 52n))) {
      mant <<= 1n;
      exp -= 1;
    }
    exp += 1;
  } else {
    mant |= 1n << 52n;
  }
  let e = BigInt(exp - 1023);
  let m = mant << (P - 52n); // in [1, 2) as fixed point
  if (m > SQRT2_FP) {
    m >>= 1n;
    e += 1n;
  }
  const z = ((m - ONE) << P) / (m + ONE);
  const fixed = e * LN2 + 2n * atanhSeries(z);
  return Number(fixed) * 2 ** -200;
}

/** Python's range(start, stop) as an array (for sample/choice). */
export function range(start: number, stop: number): number[] {
  const out: number[] = [];
  for (let i = start; i < stop; i++) out.push(i);
  return out;
}

// ------------------------------------------------------------------------------------------- SHA-512
const K512 = [
  "428a2f98d728ae22", "7137449123ef65cd", "b5c0fbcfec4d3b2f", "e9b5dba58189dbbc", "3956c25bf348b538",
  "59f111f1b605d019", "923f82a4af194f9b", "ab1c5ed5da6d8118", "d807aa98a3030242", "12835b0145706fbe",
  "243185be4ee4b28c", "550c7dc3d5ffb4e2", "72be5d74f27b896f", "80deb1fe3b1696b1", "9bdc06a725c71235",
  "c19bf174cf692694", "e49b69c19ef14ad2", "efbe4786384f25e3", "0fc19dc68b8cd5b5", "240ca1cc77ac9c65",
  "2de92c6f592b0275", "4a7484aa6ea6e483", "5cb0a9dcbd41fbd4", "76f988da831153b5", "983e5152ee66dfab",
  "a831c66d2db43210", "b00327c898fb213f", "bf597fc7beef0ee4", "c6e00bf33da88fc2", "d5a79147930aa725",
  "06ca6351e003826f", "142929670a0e6e70", "27b70a8546d22ffc", "2e1b21385c26c926", "4d2c6dfc5ac42aed",
  "53380d139d95b3df", "650a73548baf63de", "766a0abb3c77b2a8", "81c2c92e47edaee6", "92722c851482353b",
  "a2bfe8a14cf10364", "a81a664bbc423001", "c24b8b70d0f89791", "c76c51a30654be30", "d192e819d6ef5218",
  "d69906245565a910", "f40e35855771202a", "106aa07032bbd1b8", "19a4c116b8d2d0c8", "1e376c085141ab53",
  "2748774cdf8eeb99", "34b0bcb5e19b48a8", "391c0cb3c5c95a63", "4ed8aa4ae3418acb", "5b9cca4f7763e373",
  "682e6ff3d6b2b8a3", "748f82ee5defb2fc", "78a5636f43172f60", "84c87814a1f0ab72", "8cc702081a6439ec",
  "90befffa23631e28", "a4506cebde82bde9", "bef9a3f7b2c67915", "c67178f2e372532b", "ca273eceea26619c",
  "d186b8c721c0c207", "eada7dd6cde0eb1e", "f57d4f7fee6ed178", "06f067aa72176fba", "0a637dc5a2c898a6",
  "113f9804bef90dae", "1b710b35131c471b", "28db77f523047d84", "32caab7b40c72493", "3c9ebe0a15c9bebc",
  "431d67c49c100d4c", "4cc5d4becb3e42b6", "597f299cfc657e2a", "5fcb6fab3ad6faec", "6c44198c4a475817",
].map((h) => BigInt("0x" + h));
const H512 = [
  "6a09e667f3bcc908", "bb67ae8584caa73b", "3c6ef372fe94f82b", "a54ff53a5f1d36f1",
  "510e527fade682d1", "9b05688c2b3e6c1f", "1f83d9abfb41bd6b", "5be0cd19137e2179",
].map((h) => BigInt("0x" + h));
const MASK = (1n << 64n) - 1n;
const rotr = (x: bigint, n: bigint) => ((x >> n) | (x << (64n - n))) & MASK;

/** Plain SHA-512 (synchronous; only used for the seed of a few levels, so BigInt speed is fine). */
export function sha512(msg: Uint8Array): Uint8Array {
  const bitLen = BigInt(msg.length) * 8n;
  const padLen = (((msg.length + 17 + 127) >> 7) << 7);
  const data = new Uint8Array(padLen);
  data.set(msg);
  data[msg.length] = 0x80;
  for (let i = 0; i < 16; i++) data[padLen - 1 - i] = Number((bitLen >> BigInt(8 * i)) & 0xffn);
  const h = H512.slice();
  const w = new Array<bigint>(80);
  for (let off = 0; off < padLen; off += 128) {
    for (let t = 0; t < 16; t++) {
      let v = 0n;
      for (let b = 0; b < 8; b++) v = (v << 8n) | BigInt(data[off + t * 8 + b]);
      w[t] = v;
    }
    for (let t = 16; t < 80; t++) {
      const s0 = rotr(w[t - 15], 1n) ^ rotr(w[t - 15], 8n) ^ (w[t - 15] >> 7n);
      const s1 = rotr(w[t - 2], 19n) ^ rotr(w[t - 2], 61n) ^ (w[t - 2] >> 6n);
      w[t] = (w[t - 16] + s0 + w[t - 7] + s1) & MASK;
    }
    let [a, b, c, d, e, f, g, hh] = h;
    for (let t = 0; t < 80; t++) {
      const S1 = rotr(e, 14n) ^ rotr(e, 18n) ^ rotr(e, 41n);
      const ch = (e & f) ^ (~e & MASK & g);
      const t1 = (hh + S1 + ch + K512[t] + w[t]) & MASK;
      const S0 = rotr(a, 28n) ^ rotr(a, 34n) ^ rotr(a, 39n);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const t2 = (S0 + maj) & MASK;
      hh = g;
      g = f;
      f = e;
      e = (d + t1) & MASK;
      d = c;
      c = b;
      b = a;
      a = (t1 + t2) & MASK;
    }
    h[0] = (h[0] + a) & MASK;
    h[1] = (h[1] + b) & MASK;
    h[2] = (h[2] + c) & MASK;
    h[3] = (h[3] + d) & MASK;
    h[4] = (h[4] + e) & MASK;
    h[5] = (h[5] + f) & MASK;
    h[6] = (h[6] + g) & MASK;
    h[7] = (h[7] + hh) & MASK;
  }
  const out = new Uint8Array(64);
  for (let i = 0; i < 8; i++) for (let b = 0; b < 8; b++) out[i * 8 + b] = Number((h[i] >> BigInt(56 - 8 * b)) & 0xffn);
  return out;
}
