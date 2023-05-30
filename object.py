"""PIRATE GAME

    Module name: 
            object.py

    Doc:
            This module contains the bullet and chest class.
            Responsible for bullet movement/collision detection and chest logic.

    Classes:
            pygame.sprite.Sprite(builtins.object)
            Bullet

        author: Leon von Detten
        date: 19.04.2023
        version: 1.0.0
        license: free

"""


import pygame
from pygame import *
from loguru import logger

class Bullet(pygame.sprite.Sprite):
    """Bullet:
        * create and instantiate bullet object
        * handle bullet movement
        * handle bullet/__world collision 

    Args:
        pygame.sprite.Sprite (class): simple base class for visible game objects from pygame

    Returns:
        none

    """

    __speed = 20

    def __init__(self, start_x, start_y, width, height, direction, world):#DOCString ARGS WEITER MACHEN
        """__init__(constructor):
            * Initialize bullet object

        Args:
            * self (object): player object
            * start_x (int): x position of bullet
            * start_y (int): y position of bullet
            * width (int): width of bullet
            * height (int): height of bullet
            * direction (int): direction of bullet
            * world (object): world object
            
        Returns:
            none

        Tests:
            * Reight initialization of bullet object
                - correct start position
                - correct direction

        """

        pygame.sprite.Sprite.__init__(self)

        self.__direction = direction
        self.__world = world

        self.image = pygame.transform.scale(pygame.image.load("img/bullet_img/bullet.png"), (width, height))
        self.bulletPos = pygame.Rect(start_x, start_y, width, height)
        self.rect = self.image.get_rect()
        self.rect.x = start_x
        self.rect.y = start_y
        
        logger.info("Created bullet object")


    def update(self):
        self.collision() 
        self.movement()   
        self.checkFlightDistance()
        
        
    def collision(self):
        if self.__world.check_object_collision_sideblock(self.bulletPos) != 1:
            self.kill()
            logger.info("Bullet collided with block. Got destroyed")


    def checkFlightDistance(self):
        if self.bulletPos.x > self.__world.player.playerPos.x + 1220 or self.bulletPos.x < self.__world.player.playerPos.x - 1000:
            self.kill()
            logger.info("Bullet flew to long. Got destroyed")        
    
    
    def movement(self):
        self.bulletPos.x += self.__direction * self.__speed
        self.rect.x = self.bulletPos.x - self.__world.player.getCamOffset() 

class Chest(pygame.sprite.Sprite):
    """Chest:
        * create and instantiate chest object
        * doing chest animation
        * handle collision between player and chestobject

    Args:
        pygame.sprite.Sprite (class): simple base class for visible game objects from pygame

    Returns:
        none

    """
    
    def __init__(self, world, position_x, position_y, chunk, width, height):
        """__init__(constructor):
            * Initialize chest object

        Args:
            * self (object): player object
            * world (object): world object
            * position_x (int): x position of chest
            * position_y (int): y position of chest
            * chunk (int): chunk in which the chest is spawned
            * width (int): width of chest
            * height (int): height of chest
            
        Returns:
            none

        Tests:
            * Reight initialization of chest object
                - correct position
                - correct width and height

        """

        self.__spriteLoopSpeed = 0.2

        self.__chunk = chunk
        self.width = width
        self.height = height
        self.__world = world

        pygame.sprite.Sprite.__init__(self)

        self.__currentSprite = 0
        self.__chestSprites = []
        self.loadSprites()

        self.__gotOpened = False

        self.image = self.__chestSprites[self.__currentSprite]
        self.chestPos = pygame.Rect(position_x, position_y, width, height)
        self.rect = self.image.get_rect()
        self.rect.x = position_x
        self.rect.y = position_y


    def update(self):
        self.collision()
        self.rect.x = self.chestPos.x - self.__world.player.getCamOffset() #KOmmentieren: update position wo auf bilschcimr geupdated werden muss

    
    def loadSprites(self):
        for i in range(10):
            self.__chestSprites.append(pygame.transform.scale(pygame.image.load("img/chest_img/chest1_" + str(i) + ".png"), (self.width, self.height)))


    def collision(self):
        if self.__gotOpened == False:
            if self.__world.player.playerPos.colliderect(self.chestPos) == True:
                self.animation()
            else:
                self.__currentSprite = 0
            self.image = self.__chestSprites[int(self.__currentSprite)] # Chestpicture wird geupdated


    def animation(self):
        self.__currentSprite += self.__spriteLoopSpeed
        if (self.__currentSprite >= len(self.__chestSprites) - self.__spriteLoopSpeed):  #Index des aktuellen Bildes muss kleiner als anzahl aller Bilder - 1 sein sein
            self.__gotOpened = True
            logger.info("Chest got opened")

    def getChunk(self):
        return self.__chunk
    
