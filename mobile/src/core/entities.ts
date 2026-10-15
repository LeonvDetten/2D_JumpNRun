// Port of jumpnrun/core/entities.py: pure state + physics.
// Axis-separated AABB resolution against the tile grid: move x, push out, then move y, push out.

import {
  BULLET_H,
  BULLET_SPEED,
  BULLET_W,
  ENEMY_ACTIVATION_DIST,
  ENEMY_H,
  ENEMY_SPEED,
  ENEMY_W,
  GRAVITY,
  MAX_FALL_SPEED,
  PLAYER_H,
  PLAYER_W,
  TILE,
  fdiv,
} from "./constants";
import type { Level } from "./level";

export class Body {
  vx = 0;
  vy = 0;
  onGround = false;

  constructor(
    public x: number,
    public y: number,
    public w: number,
    public h: number,
  ) {}

  /** Move by vx, stop at blocks / level borders. Returns true if blocked. */
  moveX(level: Level): boolean {
    if (this.vx === 0) return false;
    this.x += this.vx;
    let blocked = false;
    if (this.x < 0) {
      this.x = 0;
      blocked = true;
    } else if (this.x > level.pixelWidth - this.w) {
      this.x = level.pixelWidth - this.w;
      blocked = true;
    }
    if (level.overlapsSolid(this.x, this.y, this.w, this.h)) {
      if (this.vx > 0) this.x = fdiv(this.x + this.w - 1, TILE) * TILE - this.w;
      else this.x = (fdiv(this.x, TILE) + 1) * TILE;
      blocked = true;
    }
    return blocked;
  }

  /** Move by vy, land on / bump against blocks, then apply gravity. */
  moveY(level: Level): void {
    if (this.vy !== 0) {
      this.y += this.vy;
      if (level.overlapsSolid(this.x, this.y, this.w, this.h)) {
        if (this.vy > 0) this.y = fdiv(this.y + this.h - 1, TILE) * TILE - this.h;
        else this.y = (fdiv(this.y, TILE) + 1) * TILE;
        this.vy = 0;
      }
    }
    this.onGround = level.overlapsSolid(this.x, this.y + 1, this.w, this.h);
    if (this.onGround && this.vy >= 0) this.vy = 0;
    else this.vy = Math.min(this.vy + GRAVITY, MAX_FALL_SPEED);
  }

  overlaps(o: { x: number; y: number; w: number; h: number }): boolean {
    return this.x < o.x + o.w && o.x < this.x + this.w && this.y < o.y + o.h && o.y < this.y + this.h;
  }

  protected copyBodyInto(other: Body): void {
    other.vx = this.vx;
    other.vy = this.vy;
    other.onGround = this.onGround;
  }
}

export class Player extends Body {
  facing = 1;
  shootCooldown = 0;
  lastShotFrame = -10_000;
  lastJumpFrame = -10_000;

  constructor(x: number, y: number) {
    super(x, y, PLAYER_W, PLAYER_H);
  }

  clone(): Player {
    const o = new Player(this.x, this.y);
    this.copyBodyInto(o);
    o.facing = this.facing;
    o.shootCooldown = this.shootCooldown;
    o.lastShotFrame = this.lastShotFrame;
    o.lastJumpFrame = this.lastJumpFrame;
    return o;
  }
}

/** Walks left/right, turns at walls, walks off ledges (and may fall into pits). */
export class Enemy extends Body {
  active = false;
  alive = true;

  constructor(
    x: number,
    y: number,
    public direction = 1,
    public wake = ENEMY_ACTIVATION_DIST,
  ) {
    super(x, y, ENEMY_W, ENEMY_H);
  }

  update(level: Level): void {
    this.vx = this.direction * ENEMY_SPEED;
    if (this.moveX(level)) this.direction = -this.direction;
    this.moveY(level);
    if (this.y > level.pixelHeight) this.alive = false;
  }

  clone(): Enemy {
    const o = new Enemy(this.x, this.y, this.direction, this.wake);
    this.copyBodyInto(o);
    o.active = this.active;
    o.alive = this.alive;
    return o;
  }
}

export class Bullet {
  readonly w = BULLET_W;
  readonly h = BULLET_H;
  startX: number;
  alive = true;

  constructor(
    public x: number,
    public y: number,
    public direction: number,
  ) {
    this.startX = x;
  }

  update(level: Level, maxRange: number): void {
    this.x += this.direction * BULLET_SPEED;
    if (Math.abs(this.x - this.startX) > maxRange || level.overlapsSolid(this.x, this.y, this.w, this.h)) {
      this.alive = false;
    }
  }

  overlaps(o: Body): boolean {
    return this.x < o.x + o.w && o.x < this.x + this.w && this.y < o.y + o.h && o.y < this.y + this.h;
  }

  clone(): Bullet {
    const o = new Bullet(this.x, this.y, this.direction);
    o.startX = this.startX;
    o.alive = this.alive;
    return o;
  }
}
