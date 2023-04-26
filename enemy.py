import pygame
from pygame import *
from loguru import logger

class Enemy(pygame.sprite.Sprite):

    def __init__(self, world, start_x, start_y, width, height, direction):
        pygame.sprite.Sprite.__init__(self)

        self.world = world
        self.width = width
        self.height = height
        self.direction = direction
        self.speed_x = 5
        self.speed_y = 0
        self.spriteLoopSpeed = 0.3

        self.currentSprite = 0
        self.runRightSprites = []
        self.runLeftSprites = []
        self.loadSprites()

        self.enemyPos = pygame.Rect(start_x, start_y, width, height)
        self.image = self.runRightSprites[self.currentSprite]
        self.rect = self.image.get_rect()
        self.rect.x = start_x
        self.rect.y = start_y
        self.base = pygame.Rect(start_x, start_y + height, width, 2)
        
        logger.info("Created enemy object")

    def update(self):
        self.movement()
        self.animation()
        self.move_y()

    def loadSprites(self):
        for image in range(3):
            enemy = pygame.image.load('img/enemy_image/e1_r' + str(image) + '.png')
            self.runRightSprites.append(pygame.transform.scale(enemy, (self.width, self.height)))
        for image in range(3):
            enemy = pygame.image.load('img/enemy_image/e1_l' + str(image) + '.png')
            self.runLeftSprites.append(pygame.transform.scale(enemy, (self.width, self.height)))    

    def movement(self):
        self.enemyPos.x += (self.direction * self.speed_x)  
        self.base.x = self.enemyPos.x
        self.rect.x = self.enemyPos.x - self.world.player.getCamOffset() 
       
    def animation(self):
        if self.direction == 1:
            self.image = self.runRightSprites[int(self.currentSprite)]
        elif self.direction == -1:
            self.image = self.runLeftSprites[int(self.currentSprite)]

        self.currentSprite += self.spriteLoopSpeed
        if self.currentSprite >= len(self.runRightSprites):
            self.currentSprite = 0      

    def move_y(self):
        collided_y = self.world.collided_get_y(self.base)
        if self.speed_y < 0 or collided_y < 0:            
            self.enemyPos.y += self.speed_y    
            self.speed_y += self.world.gravity
        if self.speed_y >= 0 and collided_y > 0:                 
            self.enemyPos.y = collided_y                                             
            self.speed_y = 0
        self.base.y = self.enemyPos.y + self.height                                                                    
        self.rect.y = self.enemyPos.y