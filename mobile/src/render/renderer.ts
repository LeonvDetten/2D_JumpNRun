// Port of jumpnrun/render/renderer.py: draws a Simulation in world units. Rendering never changes game state.
// The game runs at 30 frames per second; positions are interpolated between the last two frames so the
// picture moves smoothly at the display rate (purely visual, the simulation stays exact).

import { BULLET_H, BULLET_W, CAMERA_PLAYER_X, CHEST_H, CHEST_W, ENEMY_H, ENEMY_W, PLAYER_H, PLAYER_W, ROWS, SCREEN_H, SCREEN_W, SHOOT_COOLDOWN, TILE } from "../core/constants";
import type { Bullet, Enemy, Player } from "../core/entities";
import type { Level } from "../core/level";
import type { Simulation } from "../core/sim";
import { Assets, PLAYER_FRAMES, drawSprite, type PlayerState, type Tint } from "./assets";

export const SPRITE_LOOP_SPEED = 0.3;

/** Positions before the last simulation frame (for interpolation). */
export class Snapshot {
  px = 0;
  py = 0;
  readonly enemies = new Map<Enemy, [number, number]>();
  readonly bullets = new Map<Bullet, [number, number]>();

  static of(sim: Simulation): Snapshot {
    const s = new Snapshot();
    s.px = sim.player.x;
    s.py = sim.player.y;
    for (const e of sim.enemies) s.enemies.set(e, [e.x, e.y]);
    for (const b of sim.bullets) s.bullets.set(b, [b.x, b.y]);
    return s;
  }
}

export interface View {
  /** Interpolation between the snapshot (0) and the current state (1). */
  alpha: number;
  prev: Snapshot | null;
}

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

/** Interpolated player position. Big jumps (respawn) are not smoothed. */
export function playerPos(sim: Simulation, view: View | null): [number, number] {
  const p = sim.player;
  if (!view?.prev || Math.abs(view.prev.px - p.x) > TILE || Math.abs(view.prev.py - p.y) > TILE) return [p.x, p.y];
  return [lerp(view.prev.px, p.x, view.alpha), lerp(view.prev.py, p.y, view.alpha)];
}

/**
 * Screen x of the player. Phones are wider than the desktop's 1520 units: the view ahead stays exactly as on the
 * desktop (1220 units) and the extra width goes behind the player - which also keeps the pirate out from under
 * the thumb on the walking stick.
 */
export function playerScreenX(viewW: number): number {
  return Math.max(CAMERA_PLAYER_X, viewW - (SCREEN_W - CAMERA_PLAYER_X));
}

/** Camera follows the player and stops at the level borders. */
export function cameraX(level: Level, focusX: number, viewW: number): number {
  const cam = focusX - playerScreenX(viewW);
  return Math.max(0, Math.min(cam, Math.max(0, level.pixelWidth - viewW)));
}

export function playerSpriteState(player: Player, frame: number): [PlayerState, number] {
  const sinceShot = frame - player.lastShotFrame;
  if (sinceShot < SHOOT_COOLDOWN) return ["ATTACK", Math.min(3 + Math.trunc(sinceShot * SPRITE_LOOP_SPEED), PLAYER_FRAMES - 1)];
  if (!player.onGround) return ["JUMP", Math.min(Math.trunc((frame - player.lastJumpFrame) * SPRITE_LOOP_SPEED), PLAYER_FRAMES - 1)];
  return [player.vx !== 0 ? "RUN" : "IDLE", Math.trunc(frame * SPRITE_LOOP_SPEED) % PLAYER_FRAMES];
}

export class Renderer {
  /** Device pixels per world unit (to snap the camera and avoid seams between blocks). */
  pixelScale = 1;

  constructor(readonly assets: Assets) {}

  snap(v: number): number {
    return Math.round(v * this.pixelScale) / this.pixelScale;
  }

  drawBackground(ctx: CanvasRenderingContext2D, viewW: number): void {
    ctx.drawImage(this.assets.background, 0, 0, viewW, SCREEN_H);
  }

  drawLevel(ctx: CanvasRenderingContext2D, level: Level, cam: number, viewW: number): void {
    this.drawBackground(ctx, viewW);
    const c0 = Math.max(Math.floor(cam / TILE), 0);
    const c1 = Math.min(Math.floor((cam + viewW) / TILE) + 1, level.cols);
    const block = this.assets.sprite("block");
    for (let r = 0; r < ROWS; r++) {
      const row = level.solid[r];
      const y = r * TILE;
      for (let c = c0; c < c1; c++) {
        // 0.5 px overlap hides hairline seams when the canvas is scaled
        if (row[c]) ctx.drawImage(block.img, block.sx, block.sy, block.sw, block.sh, c * TILE - cam, y, TILE + 0.5, TILE + 0.5);
      }
    }
  }

  drawChests(ctx: CanvasRenderingContext2D, level: Level, cam: number, openFrames = 0): void {
    const index = Math.min(Math.trunc(openFrames * 0.2), 9);
    const s = this.assets.sprite(`chest_${index}`);
    for (const [cx, cy] of level.chests) drawSprite(ctx, s, cx - cam, cy, CHEST_W, CHEST_H);
  }

  drawSimObjects(ctx: CanvasRenderingContext2D, sim: Simulation, cam: number, viewW: number, view: View | null = null): void {
    const enemyIndex = Math.trunc(sim.frame * SPRITE_LOOP_SPEED) % 3;
    for (const e of sim.enemies) {
      let x = e.x;
      let y = e.y;
      const prev = view?.prev?.enemies.get(e);
      if (prev && view) {
        x = lerp(prev[0], e.x, view.alpha);
        y = lerp(prev[1], e.y, view.alpha);
      }
      if (x - cam > -TILE && x - cam < viewW) drawSprite(ctx, this.assets.sprite(`enemy_${e.direction}_${enemyIndex}`), x - cam, y, ENEMY_W, ENEMY_H);
    }
    const bullet = this.assets.sprite("bullet");
    for (const b of sim.bullets) {
      let x = b.x;
      const prev = view?.prev?.bullets.get(b);
      if (prev && view) x = lerp(prev[0], b.x, view.alpha);
      drawSprite(ctx, bullet, x - cam, b.y, BULLET_W, BULLET_H);
    }
  }

  drawPlayer(ctx: CanvasRenderingContext2D, sim: Simulation, cam: number, view: View | null = null, tint: Tint = "none", alpha = 1): void {
    const [state, index] = playerSpriteState(sim.player, sim.frame);
    const [x, y] = playerPos(sim, view);
    if (alpha < 1) ctx.globalAlpha = alpha;
    drawSprite(ctx, this.assets.player(state, index, tint), x - cam, y, PLAYER_W, PLAYER_H, sim.player.facing < 0);
    if (alpha < 1) ctx.globalAlpha = 1;
  }

  /** A complete frame of one simulation (level, chest, enemies, bullets, player). */
  draw(ctx: CanvasRenderingContext2D, sim: Simulation, viewW: number, view: View | null = null, chestOpen = 0): number {
    const [px] = playerPos(sim, view);
    const cam = this.snap(cameraX(sim.level, px, viewW));
    this.drawLevel(ctx, sim.level, cam, viewW);
    this.drawChests(ctx, sim.level, cam, chestOpen);
    this.drawSimObjects(ctx, sim, cam, viewW, view);
    this.drawPlayer(ctx, sim, cam, view);
    return cam;
  }
}
