"""Sound effects and music, synthesized with numpy (no audio files, no licences).

    audio = Audio(settings)      # silent if there is no audio device
    audio.play("jump")
    audio.music("game")

Effects are short chiptune-style waveforms; the music is a 4-chord loop (bass, arpeggio, drums) rendered once.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np

RATE = 44100


def _env(n: int, attack: float = 0.005, release: float = 0.05) -> np.ndarray:
    t = np.arange(n) / RATE
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    r = np.clip((n / RATE - t) / max(release, 1e-4), 0, 1)
    return a * r


def _osc(freq, n: int, wave: str = "square", duty: float = 0.5) -> np.ndarray:
    """freq: a number or an array of n frequencies (sweeps)."""

    freq = np.broadcast_to(np.asarray(freq, dtype=np.float64), (n,))
    phase = np.cumsum(freq) / RATE
    frac = phase % 1.0
    if wave == "square":
        return np.where(frac < duty, 1.0, -1.0)
    if wave == "triangle":
        return 4.0 * np.abs(frac - 0.5) - 1.0
    if wave == "saw":
        return 2.0 * frac - 1.0
    return np.sin(2 * np.pi * phase)


def _noise(n: int, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).uniform(-1, 1, n)


def _sweep(f0: float, f1: float, n: int) -> np.ndarray:
    return f0 * (f1 / f0) ** np.linspace(0, 1, n)


def _secs(s: float) -> int:
    return int(RATE * s)


def note(name: str) -> float:
    """'A4' -> 440.0 (sharps with '#')."""

    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names.index(pitch) + 12 * (octave - 4) - 9) / 12)


def effects() -> Dict[str, np.ndarray]:
    """name -> mono float waveform in [-1, 1]."""

    out = {}
    n = _secs(0.14)
    out["jump"] = 0.35 * _osc(_sweep(260, 720, n), n, "square", 0.25) * _env(n, 0.003, 0.06)
    n = _secs(0.16)
    out["shoot"] = (0.25 * _noise(n, 1) + 0.25 * _osc(_sweep(1200, 180, n), n, "saw")) * _env(n, 0.001, 0.12)
    n = _secs(0.18)
    out["stomp"] = (0.6 * _osc(_sweep(220, 50, n), n, "sine") + 0.2 * _noise(n, 2) * np.exp(-np.arange(n) / 800)) \
        * _env(n, 0.001, 0.1)
    n = _secs(0.22)
    out["hit"] = 0.3 * _osc(_sweep(900, 120, n), n, "square", 0.4) * _env(n, 0.001, 0.15)
    n = _secs(0.6)
    out["death"] = 0.35 * _osc(_sweep(500, 60, n), n, "triangle") * _env(n, 0.005, 0.3)
    out["win"] = _arpeggio(["C5", "E5", "G5", "C6", "E6", "G6"], 0.09, 0.55)
    out["lose"] = _arpeggio(["G4", "D#4", "C4", "G3"], 0.16, 0.5, wave="triangle")
    n = _secs(0.05)
    out["click"] = 0.3 * _osc(1400, n, "square", 0.3) * _env(n, 0.001, 0.04)
    n = _secs(0.03)
    out["hover"] = 0.12 * _osc(2100, n, "sine") * _env(n, 0.001, 0.025)
    n = _secs(0.15)
    out["beep"] = 0.3 * _osc(660, n, "square", 0.5) * _env(n, 0.002, 0.08)
    n = _secs(0.45)
    out["go"] = 0.32 * _osc(1320, n, "square", 0.5) * _env(n, 0.002, 0.3)
    n = _secs(0.35)
    out["star"] = 0.25 * (_osc(note("E6"), n, "sine") + 0.5 * _osc(note("B6"), n, "sine")) * _env(n, 0.002, 0.3)
    n = _secs(0.6)
    out["chest"] = _arpeggio(["G5", "C6", "E6"], 0.07, 0.4, wave="sine")
    return out


def _arpeggio(notes, step: float, tail: float, wave: str = "square") -> np.ndarray:
    total = _secs(step * len(notes) + tail)
    out = np.zeros(total)
    for i, name in enumerate(notes):
        start = _secs(step * i)
        n = min(_secs(step + tail * 0.6), total - start)
        out[start:start + n] += 0.22 * _osc(note(name), n, wave, 0.5) * _env(n, 0.003, tail * 0.5)
    return out


def music(kind: str = "game") -> np.ndarray:
    """A seamless loop: Am - F - C - G, two times; 'menu' is slower and without drums."""

    bpm = 132 if kind == "game" else 96
    beat = 60.0 / bpm
    chords = [("A2", ["A4", "C5", "E5"]), ("F2", ["F4", "A4", "C5"]), ("C3", ["G4", "C5", "E5"]), ("G2", ["G4", "B4", "D5"])]
    bar = _secs(beat * 4)
    out = np.zeros(bar * len(chords) * 2)
    eighth = _secs(beat / 2)
    for rep in range(2):
        for ci, (bass, arp) in enumerate(chords):
            base = (rep * len(chords) + ci) * bar
            for b in range(8):  # bass on eighths
                n = eighth
                f = note(bass) * (2 if b % 4 == 3 else 1)
                out[base + b * n: base + (b + 1) * n] += 0.16 * _osc(f, n, "triangle") * _env(n, 0.004, 0.03)
            for s in range(16):  # arpeggio on sixteenths
                n = eighth // 2
                f = note(arp[(s + (s // 4)) % 3]) * (2 if kind == "menu" and s % 8 == 7 else 1)
                start = base + s * n
                out[start:start + n] += (0.05 if kind == "game" else 0.06) * _osc(f, n, "square", 0.25) \
                    * _env(n, 0.002, 0.05)
            if kind == "game":
                for b in range(4):
                    n = _secs(0.12)
                    k = base + b * _secs(beat)
                    out[k:k + n] += 0.35 * _osc(_sweep(150, 45, n), n, "sine") * _env(n, 0.001, 0.08)  # kick
                    h = k + _secs(beat / 2)
                    m = _secs(0.04)
                    out[h:h + m] += 0.05 * _noise(m, b) * _env(m, 0.001, 0.03)  # hi-hat
                    if b in (1, 3):
                        m = _secs(0.1)
                        out[k:k + m] += 0.12 * _noise(m, 10 + b) * _env(m, 0.001, 0.08)  # snare
    return out


def to_stereo_int16(wave: np.ndarray) -> np.ndarray:
    pcm = (np.clip(wave, -1, 1) * 32000).astype(np.int16)
    return np.ascontiguousarray(np.stack([pcm, pcm], axis=1))


class Audio:
    """Plays the synthesized sounds; does nothing if pygame has no audio device."""

    def __init__(self, settings: dict):
        self.settings = settings
        self.enabled = False
        self.sounds = {}
        self.tracks = {}
        self.current: Optional[str] = None
        self._music_channel = None
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 2, 512)
            pygame.mixer.set_num_channels(16)
            for name, wave in effects().items():
                self.sounds[name] = pygame.sndarray.make_sound(to_stereo_int16(wave))
            for kind in ("menu", "game"):
                self.tracks[kind] = pygame.sndarray.make_sound(to_stereo_int16(music(kind)))
            self._music_channel = pygame.mixer.Channel(15)
            pygame.mixer.set_reserved(1)
            self.enabled = True
        except Exception:  # no audio device, no mixer: the game stays silent
            self.enabled = False

    def play(self, name: str) -> None:
        if not self.enabled or name not in self.sounds:
            return
        sound = self.sounds[name]
        sound.set_volume(float(self.settings.get("sfx", 0.8)))
        sound.play()

    def music(self, kind: Optional[str]) -> None:
        if not self.enabled or kind == self.current:
            return
        self.current = kind
        self._music_channel.stop()
        if kind in self.tracks:
            self._music_channel.play(self.tracks[kind], loops=-1, fade_ms=600)
        self.update_volume()

    def update_volume(self) -> None:
        if self.enabled:
            self._music_channel.set_volume(float(self.settings.get("music", 0.5)))
