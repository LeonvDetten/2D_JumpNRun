"""PIRATE GAME

    Module name: 
            object.py

    Doc:
            This module contains the bullet class.
            Responsible for bullet movement and collision detection.

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

class Bullet(pygame.sprite.Sprite):#
    """Bullet:
        * create and instantiate bullet object
        * handle bullet movement
        * handle bullet/world collision 

    Args:
        pygame.sprite.Sprite (class): simple base class for visible game objects from pygame

    Returns:
        none

    Tests:
        * Can be initialized
        * Can be moved
        * Bullet gets destroyed when colliding with block or flying to far

    """

    __speed = 20

    def __init__(self, start_x, start_y, width, height, direction, world):
        pygame.sprite.Sprite.__init__(self)

        self.__direction = direction
        self.world = world

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
        if self.world.check_object_collision_sideblock(self.bulletPos) != 1:
            self.kill()
            logger.info("Bullet collided with block. Got destroyed")


    def checkFlightDistance(self):
        if self.bulletPos.x > self.world.player.playerPos.x + 1220 or self.bulletPos.x < self.world.player.playerPos.x - 1000:
            self.kill()
            logger.info("Bullet flew to long. Got destroyed")        
    
    
    def movement(self):
        self.bulletPos.x += self.__direction * self.__speed
        self.rect.x = self.bulletPos.x - self.world.player.getCamOffset() 