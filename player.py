import pygame
from pygame import *


player_img = 'img/player_img/2_entity_000_IDLE_000.png'

class Player(pygame.sprite.Sprite):

    def __init__(self, start_x, start_y, width, height):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.transform.scale(pygame.image.load(player_img), (width, height))
        self.playerPos = pygame.Rect(start_x, start_y, width, height)
        self.rect = self.image.get_rect()
        self.rect.x = self.getCamOffset()
        self.rect.y = start_y
        self.base = pygame.Rect(start_x, start_y + height, width, 2)        #Ground under Player
        self.player_plain = pygame.sprite.RenderPlain(self)
    
        self.speed_y = 0
        self.speed_x = 0
        self.leben = 99
        self.jump_speed = -12
        self.gravity = 1

    def getCamOffset(self):
        return self.playerPos.x - 300                                          #Player in the middle of the screen

    def setWorld(self, world):
        self.world = world

    def main(self, screen):
        self.movement()                                                                                                
        self.move_y()
        self.player_plain.draw(screen)    

    def move_y(self):
        collided_y = self.world.collided_get_y(self.base)
        if self.speed_y < 0 or collided_y <= 0:             
            self.playerPos.y = self.playerPos.y + self.speed_y    
            self.speed_y = self.speed_y + self.gravity
        if self.speed_y >= 0 and collided_y > 0 and self.world.check_player_collision_sideblock(self.playerPos) == 1:                                
            self.playerPos.y = collided_y
            self.speed_y = 0   
        self.base.y = self.playerPos.y + self.playerPos.height                                                                    
        self.rect.y = self.playerPos.y

    def movement(self):
        key_state = pygame.key.get_pressed()
        key_down_event_list = pygame.event.get(KEYDOWN)
        if len(key_down_event_list)==0:
            self.speed_x = 0
        if key_state[K_d] and self.world.check_player_collision_sideblock(self.playerPos) != -1:
            self.speed_x = 10
        if key_state[K_a] and self.world.check_player_collision_sideblock(self.playerPos) != -2:
            if self.playerPos.x > 0:
                self.speed_x = -10 
        if key_state[K_SPACE] or key_state[K_w]:
            self.jump(self.jump_speed)
        self.playerPos.x = self.playerPos.x + self.speed_x
        self.base.x = self.playerPos.x         
        self.rect.x = self.playerPos.x - self.getCamOffset()  

    def jump(self, speed):
        if self.world.collided_get_y(self.base)>0: 
            self.speed_y = speed      
          
    
        