// Plays the synthesized sounds with WebAudio. iOS only allows sound after a touch: unlock() is called on
// the first pointer release. Music and effects have their own volume (settings, 0..1).

import { effects, music } from "./synth";

export type MusicKind = "menu" | "game" | null;

export class Audio {
  private ctx: AudioContext | null = null;
  private buffers = new Map<string, AudioBuffer>();
  private tracks = new Map<string, AudioBuffer>();
  private sfxGain: GainNode | null = null;
  private musicGain: GainNode | null = null;
  private musicSource: AudioBufferSourceNode | null = null;
  private current: MusicKind = null;
  private wanted: MusicKind = null;
  ready = false;

  constructor(private readonly volumes: { music: number; sfx: number }) {}

  /** Synthesize everything (call during the loading screen). */
  init(): void {
    try {
      const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.ctx = new AC();
    } catch {
      return; // no audio: the game stays silent
    }
    const ctx = this.ctx;
    this.sfxGain = ctx.createGain();
    this.sfxGain.connect(ctx.destination);
    this.musicGain = ctx.createGain();
    this.musicGain.connect(ctx.destination);
    const toBuffer = (wave: Float32Array) => {
      const b = ctx.createBuffer(1, wave.length, ctx.sampleRate);
      const data = b.getChannelData(0);
      for (let i = 0; i < wave.length; i++) data[i] = Math.max(-1, Math.min(1, wave[i])) * 0.98;
      return b;
    };
    for (const [name, wave] of Object.entries(effects(ctx.sampleRate))) this.buffers.set(name, toBuffer(wave));
    for (const kind of ["menu", "game"] as const) this.tracks.set(kind, toBuffer(music(ctx.sampleRate, kind)));
    this.ready = true;
    this.updateVolume();
  }

  /** Must run inside a user gesture on iOS. */
  unlock(): void {
    if (this.ctx && this.ctx.state !== "running") {
      void this.ctx.resume().then(() => this.startMusic(this.wanted));
    }
  }

  /** Pause everything (app in the background). */
  suspend(): void {
    void this.ctx?.suspend();
  }

  resume(): void {
    if (this.ctx && this.ctx.state === "suspended") void this.ctx.resume();
  }

  play(name: string): void {
    if (!this.ctx || !this.sfxGain || this.ctx.state !== "running") return;
    const buffer = this.buffers.get(name);
    if (!buffer) return;
    const src = this.ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(this.sfxGain);
    src.start();
  }

  music(kind: MusicKind): void {
    this.wanted = kind;
    if (kind === this.current) return;
    this.startMusic(kind);
  }

  private startMusic(kind: MusicKind): void {
    if (!this.ctx || !this.musicGain) return;
    if (this.musicSource) {
      try {
        this.musicSource.stop();
      } catch {
        // already stopped
      }
      this.musicSource = null;
    }
    this.current = kind;
    if (!kind || this.ctx.state !== "running") {
      if (this.ctx.state !== "running") this.current = null;
      return;
    }
    const src = this.ctx.createBufferSource();
    src.buffer = this.tracks.get(kind) ?? null;
    src.loop = true;
    const fade = this.ctx.createGain();
    fade.gain.setValueAtTime(0, this.ctx.currentTime);
    fade.gain.linearRampToValueAtTime(1, this.ctx.currentTime + 0.6);
    src.connect(fade).connect(this.musicGain);
    src.start();
    this.musicSource = src;
  }

  updateVolume(): void {
    if (this.sfxGain) this.sfxGain.gain.value = this.volumes.sfx;
    if (this.musicGain) this.musicGain.gain.value = this.volumes.music;
  }
}
