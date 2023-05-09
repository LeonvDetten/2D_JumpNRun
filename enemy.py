import pygame
from pygame import *
from loguru import logger


class Enemy(pygame.sprite.Sprite):

    __speed_x = 5
    __speed_y = 0
    __spriteLoopSpeed = 0.3


    def __init__(self, world, start_x, start_y,startChunk, __width, __height, __direction):
        pygame.sprite.Sprite.__init__(self)

        self.world = world
        self.__width = __width
        self.__height = __height
        self.__direction = __direction

        self.__currentChunk = startChunk

        self.__currentSprite = 0
        self.runRightSprites = []
        self.runLeftSprites = []
        self.loadSprites()

        self.enemyPos = pygame.Rect(start_x, start_y, __width, __height)
        self.image = self.runRightSprites[self.__currentSprite]
        self.rect = self.image.get_rect()
        self.rect.x = start_x
        self.rect.y = start_y
        self.base = pygame.Rect(start_x, start_y + __height, __width, 2)
        
        logger.info("Created enemy object")


    def update(self):
        self.movement()
        self.animation()
        self.move_y()
        self.updateChunk()
        self.checkEnemyFallOutOfMap()


    def loadSprites(self):
        for image in range(3):
            enemy = pygame.image.load('img/enemy_image/e1_r' + str(image) + '.png')
            self.runRightSprites.append(pygame.transform.scale(enemy, (self.__width, self.__height)))
        for image in range(3):
            enemy = pygame.image.load('img/enemy_image/e1_l' + str(image) + '.png')
            self.runLeftSprites.append(pygame.transform.scale(enemy, (self.__width, self.__height)))    


    def movement(self):
        if self.world.check_object_collision_sideblock(self.enemyPos) == -1:
            self.__direction = -1
        elif self.world.check_object_collision_sideblock(self.enemyPos) == -2:
            self.__direction = 1    
        self.enemyPos.x += (self.__direction * self.__speed_x)  
        self.base.x = self.enemyPos.x
        self.rect.x = self.enemyPos.x - self.world.player.getCamOffset() 
       

    def animation(self):
        if self.__direction == 1:
            self.image = self.runRightSprites[int(self.__currentSprite)]
        elif self.__direction == -1:
            self.image = self.runLeftSprites[int(self.__currentSprite)]

        self.__currentSprite += self.__spriteLoopSpeed
        if self.__currentSprite >= len(self.runRightSprites):
            self.__currentSprite = 0      


    def move_y(self):
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
        self.__currentChunk = int(self.enemyPos.x / (20*60)) 


    def getCurrentChunk(self):
        return self.__currentChunk
    

    def checkEnemyFallOutOfMap(self):
        if self.enemyPos.y > 1000:
            self.kill()
            logger.info("Enemy fell out of map. Got destroyed")