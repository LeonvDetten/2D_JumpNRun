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
                    self.enemyGroup.add(Enemy(self, self.posn_x, self.posn_y, 60, 60, 1))
                self.posn_x = self.posn_x + block_size
            self.posn_y = self.posn_y + block_size    

    def update(self,screen):
        for block in self.platforms:
            screen.blit(self.block_img, (block.x-self.player.getCamOffset(), block.y))

    def main(self, screen):
        self.check_player_collision_bottomblock(self.player.playerPos)
        screen.blit(bg_img, position)
        self.update(screen) 

    def collided_get_y(self, objct_rect):                          
        return_y = -1
        for block in self.platforms:
            if block.colliderect(objct_rect):
                return_y = block.y - block.height #+ 1                
        return return_y
    
    def check_player_collision_sideblock(self, player_rect):                  #Unschöne Funktion, aber funktioniert
        for block in self.platforms:
            #print("block.y: " + str(block.y) + " player_rect.y: " + str(player_rect.y + (player_rect.height)) + " block.height: " + str(block.y + block.height))
            if block.colliderect(player_rect) and block.y < (player_rect.y + player_rect.height -1): #and (player_rect.y + player_rect.height -1) < block.y + block.height: 
                if block.x > player_rect.x:
                    return -1
                elif block.x < player_rect.x:
                    return -2
        return 1   

    def check_player_collision_bottomblock(self, player_rect): 
        for block in self.platforms:
            if block.colliderect(player_rect) and self.player.speed_y < 0 and block.y + (block.height/2) < player_rect.y:
                self.player.speed_y = 0
                player_rect.y = block.y + block.height
        