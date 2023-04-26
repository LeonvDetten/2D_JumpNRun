import pygame
from pygame import *
from loguru import logger

class Bullet(pygame.sprite.Sprite):

    def __init__(self, start_x, start_y, width, height, direction):
        pygame.sprite.Sprite.__init__(self)

        self.width = width
        self.height = height
        self.direction = direction
        self.speed = 20

        self.image = pygame.transform.scale(pygame.image.load("img/bullet_img/bullet.png"), (width, height))
        self.rect = self.image.get_rect()
        self.rect.x = start_x
        self.rect.y = start_y
        
        logger.info("Created bullet object")

    def update(self):
        self.rect.x += self.direction * self.speed
        
