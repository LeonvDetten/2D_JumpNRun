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

    __currentSprite = 0
    __shootAnimationTime = 1000
    speed_y = 0
    __speed_x = 0
    jump_speed = -10
    __movement_speed = 8
    __spriteLoopSpeed = 0.3


    def __init__(self, start_x, start_y, width, height):
        pygame.sprite.Sprite.__init__(self)
       
        self.width = width
        self.height = height

        self.__create_sprite_container()
        self.loadSprites()
        
        self.image = self.sprites['IDLE']['right'][self.__currentSprite]
        self.__currentAnimation = "idleRight"
        self.__latest_shot = 0
        self.__direction = 1

        self.playerPos = pygame.Rect(start_x, start_y, width, height)
        self.rect = self.image.get_rect()
        self.rect.x = self.getCamOffset()
        self.rect.y = start_y
        self.base = pygame.Rect(start_x, start_y + height, width, 2)        #Ground under Player
        self.player_plain = pygame.sprite.RenderPlain(self)

        self.bulletGroup = pygame.sprite.Group()

        logger.info("Created player object")


    def __create_sprite_container(self):
        self.sprites = {}
        sprite_array = ["IDLE", "RUN", "JUMP", "ATTACK"]
        for sprite in sprite_array:
            self.sprites[sprite] = { "right": [], "left": [] }


    def loadSprites(self): 
        start_time= pygame.time.get_ticks()
        animation_states = ["IDLE", "RUN", "JUMP", "ATTACK"]
        for state in animation_states:
            for image in range(7):
                player_img = pygame.image.load(f'img/player_img/2_entity_000_{state}_00{str(image)}.png')
                player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))
                self.sprites[state]["right"].append(pygame.transform.scale(player_img_cropped, (self.width, self.height)))
                self.sprites[state]["left"].append(pygame.transform.flip(pygame.transform.scale(player_img_cropped, (self.width, self.height)),True, False))

        logger.info("Loaded player sprites in " + str(pygame.time.get_ticks() - start_time) + "ms")


    def getCamOffset(self):
        return self.playerPos.x - 300                                          #Player in the middle of the screen
    

    def getCurrentChunk(self):
        return int(self.playerPos.x / (20*60))                                    #*60 because of block size


    def setWorld(self, world):
        self.world = world


    def main(self, screen):
        self.movement()                                                                                                
        self.move_y()
        self.check_enemy_collision()
        self.animation(screen)         


    def animation(self, screen):
        animation_tag = self.__currentAnimation.split("_")
        self.image = self.sprites[animation_tag[0]][animation_tag[1]][int(self.__currentSprite)]
        self.player_plain.draw(screen)


    def move_y(self):
        collided_y = self.world.collided_get_y(self.base, self.height)
        if self.speed_y < 0 or collided_y < 0 or (self.world.check_object_collision_sideblock(self.playerPos) != 1 and self.playerPos.y < 600):            
            self.playerPos.y += self.speed_y    
            self.speed_y += self.world.gravity
        if self.speed_y >= 0 and collided_y > 0 :#and self.world.check_object_collision_sideblock(self.playerPos) == 1:                  
            self.playerPos.y = collided_y                                             
            self.speed_y = 0        
        self.base.y = self.playerPos.y + self.height                                                                    
        self.rect.y = self.playerPos.y 


    def movement(self): #loggin einbauen
        """Handles the movement of the player
        MOVEMENT BASIERT AUF BUCH ... BUCH ANGEBEN 
        """
        key_state = pygame.key.get_pressed()
        key_down_event_list = pygame.event.get(KEYDOWN)
        if len(key_down_event_list)==0:
            self.__speed_x = 0   
            if self.__latest_shot + self.__shootAnimationTime < pygame.time.get_ticks(): 
                if self.world.collided_get_y(self.base, self.height) >= 0:  
                    if self.__direction == -1:                          
                        self.__currentAnimation = "IDLE_left"
                    else:
                        self.__currentAnimation = "IDLE_right"
                else:
                    if self.__direction == -1:
                        self.__currentAnimation = "JUMP_left"
                    else:
                        self.__currentAnimation = "JUMP_right"

        if key_state[K_d] and self.world.check_object_collision_sideblock(self.playerPos) != -1:
            self.__speed_x = self.__movement_speed
            self.__direction = 1
            self.__currentAnimation = "RUN_right"

        if key_state[K_a] and self.world.check_object_collision_sideblock(self.playerPos) != -2:
            if self.playerPos.x > 0:
                self.__speed_x = self.__movement_speed * -1 
                self.__direction = -1
                self.__currentAnimation = "RUN_left"

        if key_state[K_w] or key_state[K_SPACE]:
            self.jump(self.jump_speed)

        if key_state[K_RETURN] and self.__latest_shot + self.__shootAnimationTime < pygame.time.get_ticks():
            self.shoot()

        self.__currentSprite += self.__spriteLoopSpeed           #aus Vid (angeben in Docstring)
        if self.__currentSprite >= len(self.sprites['IDLE']['right']):
                self.__currentSprite = 0
        self.playerPos.x += self.__speed_x
        self.base.x = self.playerPos.x         
        self.rect.x = self.playerPos.x - self.getCamOffset()  


    def jump(self, speed):      #loggin einbauen
        if self.world.collided_get_y(self.base, self.height)>0 and self.speed_y == 0: 
            if self.__direction == -1:                          
                self.__currentAnimation = "JUMP_left"
            else:
                self.__currentAnimation = "JUMP_right"
            self.__currentSprite = 0
            self.speed_y = speed    


    def shoot(self):
        self.__currentSprite = 3
        if self.__direction == -1:
            self.__currentAnimation = "ATTACK_left"
        else:
            self.__currentAnimation = "ATTACK_right"    
        self.bulletGroup.add(Bullet(self.playerPos.x + (0.8*self.width), self.playerPos.y + (self.height*0.45), 10, 5, self.__direction, self.world))
        self.__latest_shot = pygame.time.get_ticks()     


    def check_enemy_collision(self):
        for enemy in self.world.chunkEnemyGroup:
            if enemy.enemyPos.colliderect(self.playerPos):
                if self.speed_y > 0:
                    self.speed_y = -5
                    enemy.kill()
                    logger.info("Enemy killed with jump")
                else:
                    logger.info("Player killed by enemy")
                    pygame.quit()
                    sys.exit()
                          
          
    
        