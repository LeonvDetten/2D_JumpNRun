import pygame
from pygame import *
from loguru import logger

class Bullet(pygame.sprite.Sprite):

    __speed = 20

    def __init__(self, start_x, start_y, width, height, direction, world):
        pygame.sprite.Sprite.__init__(self)

        self.width = width
        self.height = height
        self.direction = direction
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
        self.bulletPos.x += self.direction * self.__speed
        self.rect.x = self.bulletPos.x - self.world.player.getCamOffset() 