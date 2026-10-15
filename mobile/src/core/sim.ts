// Port of jumpnrun/core/sim.py: deterministic game simulation (no rendering, no input devices, no clock).
//
// Frame order (identical for human and bot):
//   1. player input   2. player moves (x, then y)   3. enemies activate / move
//   4. bullets move and hit   5. player vs enemy (stomp or death)   6. chest (win) / pit (death)

import type { Action } from "./actions";
import {
  BULLET_RANGE,
  BULLET_W,
  ENEMY_ACTIVATION_DIST,
  JUMP_SPEED,
  PLAYER_SPEED,
  SHOOT_COOLDOWN,
  STOMP_BOUNCE,
  STOMP_TOLERANCE,
  fdiv,
} from "./constants";
import { Bullet, Enemy, Player } from "./entities";
import type { Level } from "./level";

export const Status = {
  RUNNING: "running",
  WON: "won",
  DIED_PIT: "died_pit",
  DIED_ENEMY: "died_enemy",
} as const;
export type Status = (typeof Status)[keyof typeof Status];

export class Simulation {
  frame = 0;
  status: Status = Status.RUNNING;
  player!: Player;
  enemies: Enemy[] = [];
  bullets: Bullet[] = [];
  killsStomp = 0;
  killsShot = 0;
  jumps = 0;
  maxX = 0;

  constructor(
    readonly level: Level,
    skipReset = false,
  ) {
    if (!skipReset) this.reset();
  }

  reset(): void {
    this.frame = 0;
    this.status = Status.RUNNING;
    this.player = new Player(this.level.spawn[0], this.level.spawn[1]);
    const n = this.level.enemySpawns.length;
    const dirs = this.level.enemyDirections?.length ? this.level.enemyDirections : new Array<number>(n).fill(1);
    const wakes = this.level.enemyWakes?.length ? this.level.enemyWakes : new Array<number>(n).fill(ENEMY_ACTIVATION_DIST);
    const count = Math.min(n, dirs.length, wakes.length);
    this.enemies = [];
    for (let i = 0; i < count; i++) {
      const [x, y] = this.level.enemySpawns[i];
      this.enemies.push(new Enemy(x, y, dirs[i], wakes[i]));
    }
    this.bullets = [];
    this.killsStomp = 0;
    this.killsShot = 0;
    this.jumps = 0;
    this.maxX = this.player.x;
    this.settleEnemies();
  }

  /** Drop sleeping enemies onto the ground so they don't float before activation. */
  private settleEnemies(): void {
    const ph = this.level.pixelHeight;
    for (const enemy of this.enemies) {
      for (let i = 0; i < ph; i++) {
        enemy.moveY(this.level);
        if (enemy.onGround || enemy.y > ph) break;
      }
      enemy.vy = 0;
      if (enemy.y > ph) enemy.alive = false;
    }
    this.enemies = this.enemies.filter((e) => e.alive);
  }

  /** Cheap independent copy (the level is shared, it never changes). */
  clone(): Simulation {
    const o = new Simulation(this.level, true);
    o.frame = this.frame;
    o.status = this.status;
    o.player = this.player.clone();
    o.enemies = this.enemies.map((e) => e.clone());
    o.bullets = this.bullets.map((b) => b.clone());
    o.killsStomp = this.killsStomp;
    o.killsShot = this.killsShot;
    o.jumps = this.jumps;
    o.maxX = this.maxX;
    return o;
  }

  /** Advance `frames` frames with the same input. Returns the status. */
  step(action: Action, frames = 1): Status {
    for (let i = 0; i < frames; i++) {
      if (this.status !== Status.RUNNING) break;
      this.stepFrame(action);
    }
    return this.status;
  }

  private stepFrame(action: Action): void {
    const level = this.level;
    const player = this.player;

    // 1. input
    const direction = (action.right ? 1 : 0) - (action.left ? 1 : 0);
    player.vx = direction * PLAYER_SPEED;
    if (direction) player.facing = direction;
    if (action.jump && player.onGround) {
      player.vy = JUMP_SPEED;
      player.lastJumpFrame = this.frame;
      this.jumps += 1;
    }
    if (player.shootCooldown > 0) player.shootCooldown -= 1;
    else if (action.shoot) {
      const bx = player.facing > 0 ? player.x + player.w : player.x - BULLET_W;
      const by = player.y + fdiv(player.h * 45, 100);
      this.bullets.push(new Bullet(bx, by, player.facing));
      player.shootCooldown = SHOOT_COOLDOWN;
      player.lastShotFrame = this.frame;
    }

    // 2. player movement
    const prevBottom = player.y + player.h;
    player.moveX(level);
    player.moveY(level);
    if (player.x > this.maxX) this.maxX = player.x;

    // 3. enemies
    const prevTops = new Map<Enemy, number>();
    for (const enemy of this.enemies) {
      if (!enemy.active) {
        if (Math.abs(enemy.x - player.x) >= enemy.wake) continue;
        enemy.active = true;
      }
      prevTops.set(enemy, enemy.y);
      enemy.update(level);
    }

    // 4. bullets
    for (const bullet of this.bullets) {
      bullet.update(level, BULLET_RANGE);
      if (!bullet.alive) continue;
      for (const enemy of this.enemies) {
        if (enemy.alive && bullet.overlaps(enemy)) {
          enemy.alive = false;
          bullet.alive = false;
          this.killsShot += 1;
          break;
        }
      }
    }
    this.bullets = this.bullets.filter((b) => b.alive);

    // 5. player vs enemies
    const falling = player.y + player.h > prevBottom;
    for (const enemy of this.enemies) {
      if (!enemy.alive || !player.overlaps(enemy)) continue;
      const enemyTop = prevTops.get(enemy) ?? enemy.y;
      if (falling && prevBottom <= enemyTop + STOMP_TOLERANCE) {
        enemy.alive = false;
        player.vy = STOMP_BOUNCE;
        this.killsStomp += 1;
      } else {
        this.status = Status.DIED_ENEMY;
      }
    }
    this.enemies = this.enemies.filter((e) => e.alive);

    this.frame += 1;
    if (this.status !== Status.RUNNING) return;

    // 6. goal / pit
    const { x: px, y: py, w: pw, h: ph } = player;
    for (const [cx, cy, cw, ch] of level.chests) {
      if (px < cx + cw && cx < px + pw && py < cy + ch && cy < py + ph) {
        this.status = Status.WON;
        return;
      }
    }
    if (py > level.pixelHeight) this.status = Status.DIED_PIT;
  }

  /** Compact snapshot of the full dynamic state, same layout as Python's state_signature (for parity tests). */
  stateSignature(): unknown[] {
    const p = this.player;
    return [
      this.frame,
      this.status,
      [p.x, p.y, p.vx, p.vy, p.onGround, p.facing, p.shootCooldown],
      this.enemies.map((e) => [e.x, e.y, e.vy, e.direction, e.active]),
      this.bullets.map((b) => [b.x, b.y, b.direction]),
    ];
  }
}
