"""PIRATE GAME

    Module name: 
            enemy.py

    Doc:
            This module contains the enemy class.
            Responsible for enemy movement and animations.

    Classes:
            pygame.sprite.Sprite(builtins.object)
            Enemy

        author: Leon von Detten
        date: 19.04.2023
        version: 1.0.0
        license: free

"""


import pygame
from pygame import *
from loguru import logger


class Enemy(pygame.sprite.Sprite):
    """Enemy:
        * create and instantiate enemy object
        * load sprites
        * handle enemy movement
        * update enemy chunk (chunksystem)

    Args:
        pygame.sprite.Sprite (class): simple base class for visible game objects from pygame

    Returns:
        none

    """

    __speed_x = 5
    __speed_y = 0
    __spriteLoopSpeed = 0.3


    def __init__(self, world, start_x, start_y, startChunk, width, height, direction):
        """__init__(constructor):
            * Initialize enemy object

        Args:
            * world (object): world object
            * start_x (int): x position of enemy
            * start_y (int): y position of enemy
            * startChunk (int): chunk in which the enemy is spawned
            * width (int): width of enemy
            * height (int): height of enemy
            * direction (int): direction of enemy

        Returns:
            none
        
        Tests:
            * Correct initialization of bullet object
                - correct start position
                - correct width and height
            * Sprite list is not empty
            
            """
        pygame.sprite.Sprite.__init__(self)

        self.world = world
        self.__width = width
        self.__height = height
        self.__direction = direction

        self.__currentChunk = startChunk

        self.__currentSprite = 0
        self.__runRightSprites = []
        self.__runLeftSprites = []
        self.loadSprites()

        self.enemyPos = pygame.Rect(start_x, start_y, width, height)
        self.image = self.__runRightSprites[self.__currentSprite]
        self.rect = self.image.get_rect()
        self.rect.x = start_x
        self.rect.y = start_y
        self.base = pygame.Rect(start_x, start_y + height, width, 2)
        
        

    def update(self):
        """update:
            * update enemy object by calling movement, animation, move_y, updateChunk and checkEnemyFallOutOfMap methods
        
        Args:
            none

        Returns:
            none

        Tests:
            * Test if all methods are called
            * Test if methods are called with correct parameters

        """

        self.movement()
        self.animation()
        self.move_y()
        self.updateChunk()
        self.checkEnemyFallOutOfMap()


    def loadSprites(self):
        """loadSprites:
            * prload enemy sprites and append them to correct sprite list

        Args:
            none

        Returns:
            none

        Tests:
            * Sprite list is not empty
            * Sprite list contains correct sprites
                - correct sprtie image 
                - correct sprite size

        """

        for image in range(3):
            enemy = pygame.image.load('img/enemy_img/e1_r' + str(image) + '.png')
            self.__runRightSprites.append(pygame.transform.scale(enemy, (self.__width, self.__height)))
            enemy = pygame.image.load('img/enemy_img/e1_l' + str(image) + '.png')
            self.__runLeftSprites.append(pygame.transform.scale(enemy, (self.__width, self.__height)))  


    def movement(self):
        """movement:
            * handle enemy movement

        Args:
            none

        Returns:
            none

        Tests:
            * Enemy direction is set correctly after collision with block
            * Enemy position gets updated correctly

        """

        if self.world.check_object_collision_sideblock(self.enemyPos) == -1:
            self.__direction = -1
        elif self.world.check_object_collision_sideblock(self.enemyPos) == -2:
            self.__direction = 1    
        self.enemyPos.x += (self.__direction * self.__speed_x)  
        self.base.x = self.enemyPos.x
        self.rect.x = self.enemyPos.x - self.world.player.getCamOffset() 
       

    def animation(self):
        """animation:
            * handle enemy animation. Switching sprite list when direction changes

        Args:
            none

        Returns:
            none

        Tests:
            * Enemy sprite list is switched when direction changes
            * Current sprite set to 0 when sprite list is at the end

        """

        if self.__direction == 1:
            self.image = self.__runRightSprites[int(self.__currentSprite)]
        elif self.__direction == -1:
            self.image = self.__runLeftSprites[int(self.__currentSprite)]

        self.__currentSprite += self.__spriteLoopSpeed
        if self.__currentSprite >= len(self.__runRightSprites):
            self.__currentSprite = 0      


    def move_y(self):
        """move_y:
            * handles enemy y position

        Args:
            none

        Returns:
            none

        Tests:
            * Test if every condition is entered
            * Test if enemy can fall through ground

        """

        collided_y = self.world.collided_get_y(self.base, self.__height)
        if self.__speed_y < 0 or collided_y < 0:            
            self.enemyPos.y += self.__speed_y    
            self.__speed_y += self.world.gravity
        if self.__speed_y >= 0 and collided_y > 0:                 
            self.enemyPos.y = collided_y                                         
            self.__speed_y = 0
        self.base.y = self.enemyPos.y + self.__height                                                                    
        self.rect.y = self.enemyPos.y


    def updateChunk(self):
        """updateChunk:
            * update current chunk of enemy

        Args:
            none

        Returns:
            none

        Tests:
            * Enemy is in correct chunk
            * Current chunk can be updated

        """

        self.__currentChunk = int(self.enemyPos.x / (20*60)) #Gut Kommentieren


    def getCurrentChunk(self):
        """getCurrentChunk:
            * returns current chunk of enemy

        Args:
            none

        Returns:
            self.__currentChunk (int): current chunk of enemy

        Tests:
            * Test if correct chunk gets returned 

        """

        return self.__currentChunk
    

    def checkEnemyFallOutOfMap(self):
        """checkEnemyFallOutOfMap:
            * checks if enemy is falling out of map

        Args:
            none

        Returns:
            none

        Tests:
            * Test if enemy is killed when y position is greater than 1000
            * Test if enemy is not killed when y position is less than 1000

        """

        if self.enemyPos.y > 1000:
            self.kill()
            logger.info("Enemy fell out of map. Got killed")