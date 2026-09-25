"""Headless video recording (works without a screen, e.g. in the cloud)."""

from __future__ import annotations

import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "hide")

import numpy as np
import pygame

from jumpnrun.core.constants import FPS, SCREEN_H, SCREEN_W


def init_headless() -> pygame.Surface:
    """Start pygame without a window (unless a real display is already open)."""

    if not pygame.display.get_init() or pygame.display.get_surface() is None:
        if "DISPLAY" not in os.environ:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.display.init()
        pygame.display.set_mode((1, 1))
    pygame.font.init()
    return pygame.Surface((SCREEN_W, SCREEN_H))


class VideoWriter:
    """Collects pygame surfaces into an mp4 (scaled down to keep files small)."""

    def __init__(self, path: str, fps: int = FPS, scale: float = 0.5):
        import imageio

        self.size = (int(SCREEN_W * scale) // 16 * 16, int(SCREEN_H * scale) // 16 * 16)
        self._writer = imageio.get_writer(path, fps=fps, codec="libx264", quality=7, macro_block_size=16)

    def add(self, surface: pygame.Surface, repeat: int = 1) -> None:
        small = pygame.transform.smoothscale(surface, self.size)
        frame = np.transpose(pygame.surfarray.array3d(small), (1, 0, 2))
        for _ in range(repeat):
            self._writer.append_data(frame)

    def close(self) -> None:
        self._writer.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
