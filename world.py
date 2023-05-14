import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame

from enemy import *

bg_img = pygame.image.load('img/background_img/bg.jpg')
bg_img = pygame.transform.scale(bg_img, (1520, 800))
position = (0, 0)

class World:

    gravity = 1
    __chunkOffset = 20

    """
        DUMMY TEST 
    """
                                                                        #Konstruktor aus Buch (Buch angeben)
    def __init__(self, level, block_size, player):
        self.__level = level
        self.__block_size = block_size
        self.player = player
        self.__platforms = [[]]
        self.__chunkPlatforms = []

        self.enemyGroup = pygame.sprite.Group()
        self.chunkEnemyGroup = pygame.sprite.Group()

        self.block_img = pygame.image.load('img/ground_img/spaceground.png')
        self.block_img = pygame.transform.scale(self.block_img, (block_size, block_size))

        self.initializeWorld()


    def initializeWorld(self):
        pos_y = 0
        for line in self.__level:#auslagern
            pos_x = 0
            blockCount = 0
            chunk = 0
            for block in line:
                blockCount += 1
                #print(self.blockCount)
                if blockCount > self.__chunkOffset:
                    chunk += 1
                    blockCount = 0
                    if len(self.__platforms) <= chunk:
                        self.__platforms.append([])
                if block == 'B':
                    #print(chunk)
                    self.__platforms[chunk].append(pygame.Rect(pos_x, pos_y, self.__block_size, self.__block_size))
                if block =="E":
                    self.enemyGroup.add(Enemy(self, pos_x, pos_y, chunk, 40, 40, 1))
                pos_x = pos_x + self.__block_size
            pos_y = pos_y + self.__block_size  
        #print(self.__platforms)


    def update(self,screen):
        self.__chunkPlatforms = []                  
        for i in range(-1, 2):
            if self.player.getCurrentChunk() + i >= 0 and self.player.getCurrentChunk() + i < len(self.__platforms):
                self.__chunkPlatforms.extend(self.__platforms[self.player.getCurrentChunk() + i])
        for block in self.__chunkPlatforms:
            screen.blit(self.block_img, (block.x-self.player.getCamOffset(), block.y))


    def main(self, screen):
        self.check_player_collision_bottomblock(self.player.playerPos)
        screen.blit(bg_img, position)
        self.update(screen) 


    def collided_get_y(self, objct_rect, objekt_height):                          
        return_y = -1
        for block in self.__chunkPlatforms:
            if block.colliderect(objct_rect):
                return_y = block.y - objekt_height           
        return return_y
    

    def check_object_collision_sideblock(self, object_rect):                  #Unschöne Funktion, aber funktioniert
        for block in self.__chunkPlatforms:                                    
            #print("block.y: " + str(block.y) + " object_rect.y: " + str(object_rect.y + (object_rect.height)) + " block.height: " + str(block.y + block.height))
            if block.colliderect(object_rect) and block.y < (object_rect.y + object_rect.height -1): #and (object_rect.y + object_rect.height -1) < block.y + block.height: 
                if block.x > object_rect.x:
                    return -1
                elif block.x < object_rect.x:
                    return -2
        return 1   


    def check_player_collision_bottomblock(self, object_rect):
        for block in self.__chunkPlatforms:
            if block.colliderect(object_rect) and self.player.speed_y < 0 and block.y + (block.height/2) < object_rect.y:
                self.player.speed_y = 0
                object_rect.y = block.y + block.height

    
                
                

        
        