"""Game constants shared by simulation, renderer and RL code.

All distances are in pixels, all durations in frames (the game runs at FPS
frames per second). The simulation never looks at the wall clock, so the same
inputs always produce exactly the same game.
"""

FPS = 30

# World / screen
TILE = 60
ROWS = 13
SCREEN_W = 1520
SCREEN_H = 800
CAMERA_PLAYER_X = 300  # player is drawn at this screen x (camera follows)

# Player
PLAYER_W = 40
PLAYER_H = 60
PLAYER_SPEED = 8
JUMP_SPEED = -12  # apex = 12 + 11 + ... + 1 = 78 px (> 1 tile, < 2 tiles)
GRAVITY = 1
MAX_FALL_SPEED = 15  # < TILE, so nothing can tunnel through a block
STOMP_BOUNCE = -7
STOMP_TOLERANCE = 6  # px the player's feet may be below an enemy's top and still stomp
SHOOT_COOLDOWN = 30
DEFAULT_SPAWN = (2 * TILE, 50)

# Enemy
ENEMY_W = 40
ENEMY_H = 40
ENEMY_SPEED = 5
ENEMY_ACTIVATION_DIST = SCREEN_W - CAMERA_PLAYER_X  # enemies start walking when they enter the screen

# Bullet
BULLET_W = 10
BULLET_H = 5
BULLET_SPEED = 20
BULLET_RANGE = 1220

# Chest (goal)
CHEST_W = 60
CHEST_H = 40
