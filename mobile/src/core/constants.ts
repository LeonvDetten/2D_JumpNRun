// Port of jumpnrun/core/constants.py. Pixels and frames, the simulation never reads the clock.

export const FPS = 30;

// World / screen
export const TILE = 60;
export const ROWS = 13;
export const SCREEN_W = 1520;
export const SCREEN_H = 800;
export const CAMERA_PLAYER_X = 300;

// Player
export const PLAYER_W = 40;
export const PLAYER_H = 60;
export const PLAYER_SPEED = 8;
export const JUMP_SPEED = -12;
export const GRAVITY = 1;
export const MAX_FALL_SPEED = 15;
export const STOMP_BOUNCE = -7;
export const STOMP_TOLERANCE = 6;
export const SHOOT_COOLDOWN = 30;
export const DEFAULT_SPAWN: readonly [number, number] = [2 * TILE, 50];

// Enemy
export const ENEMY_W = 40;
export const ENEMY_H = 40;
export const ENEMY_SPEED = 5;
export const ENEMY_ACTIVATION_DIST = SCREEN_W - CAMERA_PLAYER_X;

// Bullet
export const BULLET_W = 10;
export const BULLET_H = 5;
export const BULLET_SPEED = 20;
export const BULLET_RANGE = 1220;

// Chest (goal)
export const CHEST_W = 60;
export const CHEST_H = 40;

/** Python's `a // b` for integers (rounds towards minus infinity, unlike JS division). */
export function fdiv(a: number, b: number): number {
  return Math.floor(a / b);
}
