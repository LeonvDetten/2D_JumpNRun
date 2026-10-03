"""PIRATE GAME

    Module name: 
            player.py

    Doc:
            This module contains the player class. 
            Responsible for player movement, animations and shooting.

    Classes:
            pygame.sprite.Sprite(builtins.object)
            Player

        author: Leon von Detten
        date: 19.04.2023
        version: 1.0.0
        license: free

"""


import pygame
from pygame import *
from loguru import logger
import sys

from object import *


class Player(pygame.sprite.Sprite):
    """Player:
        * create and instantiate player object
        * load sprites
        * handle player movement

    Args:
        pygame.sprite.Sprite (class): simple base class for visible game objects from pygame

    Returns:
        none

    """

    __currentSprite = 0
    __shootAnimationTime = 1000
    speed_y = 0
    __speed_x = 0
    # Slightly higher jump so the player can clear one-block obstacles reliably.
    jump_speed = -11
    __movement_speed = 8
    __spriteLoopSpeed = 0.3


    def __init__(self, start_x, start_y, width, height):
        """__init__(constructor):
            * Initialize player object

        Args:
            * start_x (int): x position of player
            * start_y (int): y position of player
            * width (int): width of player
            * height (int): height of player

        Returns:
            none

        Tests:
            * Correct initialization of player object
                - correct position
                - correct size
            * loadSprites and __create_sprite_container are called 

        """
        
        pygame.sprite.Sprite.__init__(self)
       
        self.width = width
        self.height = height

        self.__create_sprite_container()
        self.loadSprites()
        
        self.image = self.sprites['IDLE']['right'][self.__currentSprite]
        self.__currentAnimation = "IDLE_right"
        self.__latest_shot = 0
        self.__latest_jump_kill = 0
        self.__latest_log = 0
        self.__direction = 1

        self.playerPos = pygame.Rect(start_x, start_y, width, height)
        self.rect = self.image.get_rect()                            #Rect for player image
        self.rect.x = self.getCamOffset()
        self.rect.y = start_y
        self.base = pygame.Rect(start_x, start_y + height, width, 2)        #Ground under Player
        self.player_plain = pygame.sprite.RenderPlain(self)     

        self.bulletGroup = pygame.sprite.Group()
        self.__frozen = False

        logger.info("Created player object")


    def __create_sprite_container(self):
        """__create_sprite_container:
            * Creates sprite container for player sprites. Sprite container is a dictionary with the following structure:
                * sprite_container = {
                    "IDLE": {
                        "right": [sprite1, sprite2, sprite3, ...],
                        "left": [sprite1, sprite2, sprite3, ...]
                    },
                    "RUN": {
                        "right": [sprite1, sprite2, sprite3, ...],
                        "left": [sprite1, sprite2, sprite3, ...]
                    },
                    "JUMP": {
                        "right": [sprite1, sprite2, sprite3, ...],
                        "left": [sprite1, sprite2, sprite3, ...]
                    },
                    "ATTACK": {
                        "right": [sprite1, sprite2, sprite3, ...],
                        "left": [sprite1, sprite2, sprite3, ...]
                    }
                }

        Args:
            none            

        Returns:
            none

        Tests:
            * Correct creation of sprite container
                - correct structure
                - correct sprite names

        """

        self.sprites = {}
        sprite_array = ["IDLE", "RUN", "JUMP", "ATTACK"]
        for sprite in sprite_array:
            self.sprites[sprite] = { "right": [], "left": [] }


    def loadSprites(self): 
        """loadSprites:
            * Loads player sprites from file and adds them to sprite container

        Args:
            none

        Returns:    
            none

        Tests:
            * Correct adding of player sprites to sprite container
                - correct sprite image 
            * Time to load sprites not too long

        """

        start_time= pygame.time.get_ticks()                             #Start time of loading sprites
        animation_states = ["IDLE", "RUN", "JUMP", "ATTACK"]
        for state in animation_states:                                  #Load sprites for every animation state
            for image in range(7):
                player_img = pygame.image.load(f'img/player_img/2_entity_000_{state}_00{str(image)}.png')       #Load player sprites
                player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))                     #Crop player sprites
                self.sprites[state]["right"].append(pygame.transform.scale(player_img_cropped, (self.width, self.height)))  #Add player sprites to sprite container
                self.sprites[state]["left"].append(pygame.transform.flip(pygame.transform.scale(player_img_cropped, (self.width, self.height)),True, False))    #Add flipped player sprites to sprite container

        logger.info("Loaded player sprites in " + str(pygame.time.get_ticks() - start_time) + "ms")


    def getCamOffset(self):
        """getCamOffset:
            * Calculates camera offset used for scrolling through the world. Player is always at x-Position 300 on the screen.

        Args:
            none

        Returns:
            * int: camera offset

        Tests:
            * Correct calculation of camera offset 
                - test with diffrend enemy or block positions 

        """

        return self.playerPos.x - 300                                          #Player is always at one position of the screen
    

    def getCurrentChunk(self):
        """getCurrentChunk:
            * Calculates current chunk of player. Chunk is used to load and unload chunks of the world.

        Args:
            none

        Returns:    
            * int: current chunk

        Tests:
            * Returns correct chunk
                - compare calculated chunk from method with world chunk the player is in

        """

        return int(self.playerPos.x / (20*60))                                    #*60 because of block size


    def setWorld(self, world):
        """setWorld:
            * Sets world object as attribute of player object

        Args:
            * world (object): world object

        Returns:
            none

        Tests:  
            * Test if world object is correctly set in player object

        """

        self.world = world


    def main(self, action=None):
        """main:
            * Main method of player object. Calls most of the other methods from player class.

        Args:
            none

        Returns:
            none

        Tests:
            * Test if all methods are called
            * Test if methods are called with correct parameters

        """
            
        if self.__frozen:
            # Freeze player after chest touch while allowing chest animation to finish.
            self.__speed_x = 0
            self.speed_y = 0
            if self.__direction == -1:
                self.__currentAnimation = "IDLE_left"
            else:
                self.__currentAnimation = "IDLE_right"
            self.base.x = self.playerPos.x
            self.base.y = self.playerPos.y + self.height
            self.rect.x = self.playerPos.x - self.getCamOffset()
            self.rect.y = self.playerPos.y
            self.animation()
            return

        self.movement(action)
        self.move_y()
        self.check_enemy_collision()
        self.animation()         


    def animation(self):
        """animation:
            * Animates player object. Changes sprite of player object depending on current animation state.

        Args:
            none

        Returns:
            none

        Tests:  
            * Test if correct sprite is set depending on current Sprite
            * Test if correct sprite is set depending on current animation state

        """

        animation_tag = self.__currentAnimation.split("_")  # splitting animation: "IDLE_right" -> "IDLE", "right"  
        self.image = self.sprites[animation_tag[0]][animation_tag[1]][int(self.__currentSprite)]  # set sprite depending on animation state and sprite number  


    def move_y(self):
        """move_y:
            * Handles y-movement of player object. Checks if player object is on ground or in air.
              If player object is in air, gravity is applied. If player object is on ground, player position is set to ground position.

        Args:
            none

        Returns:
            none

        Tests:
            * Test if every condition is entered
            * Test if player can fall through ground

        """

        collided_y = self.world.collided_get_y(self.base, self.height)
        if self.speed_y < 0 or collided_y < 0 or (self.world.intersects_side_solid(self.playerPos) and self.playerPos.y < 600):
            self.playerPos.y += self.speed_y        # move player object in y-direction
            self.speed_y += self.world.gravity      # increase falling speed by gravity
        if self.speed_y >= 0 and collided_y > 0 :                
            self.playerPos.y = collided_y           # set player position above the collided block                                  
            self.speed_y = 0        
        self.base.y = self.playerPos.y + self.height        # update base position of player object                                                                    
        self.rect.y = self.playerPos.y                      # update rect position of player object


    def movement(self, action=None): 
        """movement:
            * Handles the movement of the player object. Checks for key inputs and changes the player position or calls methods. 
        Also changes the animation state of the player object.

        Args:
            none

        Returns:
            none

        Tests:
            * Test if every condition is entered
            * Test if player can press multiple keys at once 

        
        Sprite Animation and Current Sprite Logic inspired by: 
            Python / Pygame Tutorial: Animations with sprites (Clear Code)
            https://www.youtube.com/watch?v=MYaxPa_eZS0&
            
        """
        if action is None:
            key_state = pygame.key.get_pressed()
            key_down_event_list = pygame.event.get(KEYDOWN)
            move_left = key_state[K_a]
            move_right = key_state[K_d]
            jump_pressed = key_state[K_w] or key_state[K_SPACE]
            shoot_pressed = key_state[K_RETURN]
            idle_input = len(key_down_event_list) == 0
        else:
            move_left = bool(getattr(action, "left", False))
            move_right = bool(getattr(action, "right", False))
            jump_pressed = bool(getattr(action, "jump", False))
            shoot_pressed = bool(getattr(action, "shoot", False))
            idle_input = not (move_left or move_right or jump_pressed or shoot_pressed)

        if idle_input:                 # check if no input is pressed
            self.__speed_x = 0   
            if self.__latest_shot + self.__shootAnimationTime < pygame.time.get_ticks():    # check if shoot animation is over
                if self.world.collided_get_y(self.base, self.height) >= 0:                  # check if player is on ground  
                    if self.__direction == -1:                          
                        self.__currentAnimation = "IDLE_left"                           # set animation to idle left
                    else:
                        self.__currentAnimation = "IDLE_right"                          # set animation to idle right
                else:
                    if self.__direction == -1:
                        self.__currentAnimation = "JUMP_left"                       # set animation to jump left
                    else:
                        self.__currentAnimation = "JUMP_right"                      # set animation to jump right

        if move_right:
            next_rect = self.playerPos.copy()
            next_rect.x += self.__movement_speed
            if not self.world.intersects_side_solid(next_rect):
                self.__speed_x = self.__movement_speed                        # set player speed to movement speed
                self.__direction = 1
                self.__currentAnimation = "RUN_right"                         # set animation to run right
            

        if move_left:
            next_rect = self.playerPos.copy()
            next_rect.x -= self.__movement_speed
            if self.playerPos.x > 0 and not self.world.intersects_side_solid(next_rect):
                self.__speed_x = self.__movement_speed * -1            # set player speed to movement speed * -1 (negative)
                self.__direction = -1
                self.__currentAnimation = "RUN_left"                   # set animation to run left


        if jump_pressed:                  # check if jump input is pressed
            self.jump(self.jump_speed)                          # call jump method with jump speed as argument


        if shoot_pressed and self.__latest_shot + self.__shootAnimationTime < pygame.time.get_ticks():    # check if shoot input is pressed and if latest shot is 1 second ago
            self.shoot()                                                                                     # call shoot method


        self.__currentSprite += self.__spriteLoopSpeed    # increase current sprite by sprite loop speed           
        if self.__currentSprite >= len(self.sprites['IDLE']['right']):  # check if current sprite is bigger than the number of sprites in the idle animation (sprite amount is the same for every animation)
                self.__currentSprite = 0
        previous_x = self.playerPos.x
        self.playerPos.x += self.__speed_x             # move player object in x-direction
        # Safety clamp: never allow ending a frame inside side-solid blocks.
        if self.world.intersects_side_solid(self.playerPos):
            self.playerPos.x = previous_x
            self.__speed_x = 0
        self.base.x = self.playerPos.x          # update base position of player object
        self.rect.x = self.playerPos.x - self.getCamOffset()    # update rect position of player object
        self.logging_movement()                # call logging method


    def jump(self, speed):  
        """jump:
            * Handles the jump of the player object. Checks if player object is on ground and sets speed_y to the given speed (argument).
              Changes the animation state of the player object depending on the direction of the jump.

        Args:
            * speed (int): jump speed

        Returns:
            none

        Tests:
            * Test if player can jump multiple times
            * Test if player can jump while in air

        """

        if self.world.collided_get_y(self.base, self.height)>0 and self.speed_y == 0:   # check if player is on ground and if speed_y is 0
            if self.__direction == -1:      # check if player is facing left                          
                self.__currentAnimation = "JUMP_left"   # set animation to jump left
                logger.info("Player jumped left")
            else:
                self.__currentAnimation = "JUMP_right"  # set animation to jump right
                logger.info("Player jumped right")
            self.__currentSprite = 0
            self.speed_y = speed    


    def shoot(self):
        """shoot:
            * Handles the shooting of the player object. Doing the logic for the shooting (which direction) and creating a bullet object.
              Changes the animation state of the player object depending on the direction of the shot.

        Args:
            none

        Returns:
            none

        Tests:
            * Test if player can shoot multiple times in a row
            * Test if animation is correctly changed after shooting 

        """

        self.__currentSprite = 3                        # set current sprite to 3 because the shooting animation beginning with the 4th sprite looks more realistic
        if self.__direction == -1:
            self.__currentAnimation = "ATTACK_left"     # set animation to attack left
        else:
            self.__currentAnimation = "ATTACK_right"    # set animation to attack right
        self.bulletGroup.add(Bullet(self.playerPos.x + (0.8*self.width), self.playerPos.y + (self.height*0.45), 10, 5, self.__direction, self.world))   # create bullet object
        self.__latest_shot = pygame.time.get_ticks()        # set latest shot to current time     
        logger.info("Player shot")


    def logging_movement(self):
        """logging_movement:
            * Handles movement logging. Checks in which direction the player object is moving and logs the movement.

        Args:
            none

        Returns:
            none

        Tests:
            * Test how often the player object is logged ! > __logging_timeBreak
            * Test if right text is logged (Player is moving right / left)

        """

        __logging_timeBreak = 800
        if self.__speed_x > 0 and self.__latest_log + __logging_timeBreak < pygame.time.get_ticks():    # check if player is moving right and if latest log is 1 second ago
            self.__latest_log = pygame.time.get_ticks()         # set latest log to current time
            logger.info("Player is moving right")
        elif self.__speed_x < 0 and self.__latest_log + __logging_timeBreak < pygame.time.get_ticks():  # check if player is moving left and if latest log is 1 second ago
            self.__latest_log = pygame.time.get_ticks()         # set latest log to current time
            logger.info("Player is moving left")


    def check_enemy_collision(self):
        """check_enemy_collision:
            * Handles collision between player and every enemy near by. Checks how the player object collides with the enemy. Depending on the collision the game is over or the enemy object gets killed.
        Args:
            none

        Returns:
            none

        Tests:
            * Test if player can kill enemy with jump
            * Test if player can kill enemy with jump and dies meanwhile
            * Test if player gets killed by enemy while jumping

        """
        
        for enemy in self.world.chunkEnemyGroup:    # iterate through every enemy object in the chunk enemy group
            if enemy.enemyPos.colliderect(self.playerPos):  # check if enemy object collides with player object
                if self.speed_y > 0:    # check if player is jumping
                    self.speed_y = -5   # set speed_y to -5 (little jump)
                    enemy.kill()        # kill enemy object
                    logger.info("Enemy killed with jump")
                    self.__latest_jump_kill = pygame.time.get_ticks()

                elif self.speed_y <= 0 and self.__latest_jump_kill + 100 < pygame.time.get_ticks():  # check if player is not in jump and if latest jump kill is 0.1 seconds ago
                    logger.info("Player killed by enemy")   # log player death
                    if hasattr(self.world, "on_player_death") and callable(self.world.on_player_death):
                        self.world.on_player_death()
                        return
                    pygame.quit()                           # quit pygame
                    sys.exit()                              # exit program

    def get_speed_x(self):
        return self.__speed_x

    def get_direction(self):
        return self.__direction

    def set_frozen(self, frozen: bool):
        self.__frozen = bool(frozen)
                          
          
    
        
