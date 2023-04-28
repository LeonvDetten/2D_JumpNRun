import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame

from enemy import *

bg_img = pygame.image.load('img/background_img/bg.jpg')
bg_img = pygame.transform.scale(bg_img, (1520, 800))
position = (0, 0)

class World:                                                                    #Konstruktor aus Buch (Buch angeben)
    def __init__(self, level, block_size, platform_color, player):
        self.level = level
        self.block_size = block_size
        self.platform_color = platform_color
        self.player = player
        self.platforms = []
        self.posn_x = 0
        self.posn_y = 0
        self.gravity = 1

        self.enemyGroup = pygame.sprite.Group()

        self.block_img = pygame.image.load('img/ground_img/spaceground.png')
        self.block_img = pygame.transform.scale(self.block_img, (block_size, block_size))

        for line in self.level:
            self.posn_x = 0
            for block in line:
                if block == 'B':
                    self.platforms.append(pygame.Rect(self.posn_x, self.posn_y, block_size, block_size))
                if block =="E":
                    self.enemyGroup.add(Enemy(self, self.posn_x, self.posn_y, 40, 40, 1))
                self.posn_x = self.posn_x + block_size
            self.posn_y = self.posn_y + block_size    

    def update(self,screen):
        for block in self.platforms:
            screen.blit(self.block_img, (block.x-self.player.getCamOffset(), block.y))

    def main(self, screen):
        self.check_player_collision_bottomblock(self.player.playerPos)
        screen.blit(bg_img, position)
        self.update(screen) 

    def collided_get_y(self, objct_rect, objekt_height):                          
        return_y = -1
        for block in self.platforms:
            if block.colliderect(objct_rect):
                return_y = block.y - objekt_height           
        return return_y
    
    def check_object_collision_sideblock(self, object_rect):                  #Unschöne Funktion, aber funktioniert
        for block in self.platforms:
            #print("block.y: " + str(block.y) + " object_rect.y: " + str(object_rect.y + (object_rect.height)) + " block.height: " + str(block.y + block.height))
            if block.colliderect(object_rect) and block.y < (object_rect.y + object_rect.height -1): #and (object_rect.y + object_rect.height -1) < block.y + block.height: 
                if block.x > object_rect.x:
                    return -1
                elif block.x < object_rect.x:
                    return -2
        return 1   

    def check_player_collision_bottomblock(self, object_rect): 
        for block in self.platforms:
            if block.colliderect(object_rect) and self.player.speed_y < 0 and block.y + (block.height/2) < object_rect.y:
                self.player.speed_y = 0
                object_rect.y = block.y + block.height

    
                
                

        
        