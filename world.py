"""PIRATE GAME

    Module name: 
            world.py

    Doc:
            This module contains the world class.
            Mainly responsible for the world generation and collision detection.

    Classes:
            World

        author: Leon von Detten
        date: 19.04.2023
        version: 1.0.0
        license: free

"""


import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame

from enemy import *
from object import *

bg_img = pygame.image.load('img/background_img/bg.jpg')
bg_img = pygame.transform.scale(bg_img, (1520, 800))
position = (0, 0)

class World:
    """World:
        * create and instantiate world object
        * generate world (blocks, enemies)
        * handle collision detection

    Args:
        none 

    Returns:
        none

    """

    gravity = 1
    __chunkOffset = 20


    #Konstruktor aus Buch (Buch angeben)
    def __init__(self, game, block_size, player):
        """__init__(constructor):
            * Initialize world object

        Args:
            * game (object): game object
            * block_size (int): size of the blocks
            * player (object): player object

        Returns:
            none

        Tests:
            * Correct initialization of world object
                - correct level
                - correct blocksize
            * Pygame sprite groups aren't empty

        """
        self.__game = game
        self.__level = self.__game.level
        self.__block_size = block_size
        self.__enemy_size = 40
        self.__chest_size = 40
        self.player = player
        self.__platforms = [[]]
        self.__chunkPlatforms = []

        self.enemyGroup = pygame.sprite.Group()
        self.chunkEnemyGroup = pygame.sprite.Group()
        self.chestGroup = pygame.sprite.Group()

        self.block_img = pygame.image.load('img/ground_img/spaceground.png')
        self.block_img = pygame.transform.scale(self.block_img, (block_size, block_size))

        self.initializeWorld()
        logger.info("Created world object")

    ### numpy vectorized operations (.where) for collision detection
    ### https://stackoverflow.com/questions/29640685/vectorized-2d-collision-detection-in-numpy

    def initializeWorld(self):
        """initializeWorld:
            * Initialize world objects by iterating through level list

        Args:
            none

        Returns:
            none

        Tests:
            * Objects gets appended into pygame sprite groups
            * blocks are in the correct chunk


        Generating Level from list inspired by: 
            https://www.reddit.com/r/pygame/comments/12ideai/level_from_the_list/

        """

        pos_y = 0
        enemyCount = 0
        for line in self.__level:
            pos_x = 0
            blockCount = 0
            chunk = 0
            for block in line:
                blockCount += 1
                if blockCount > self.__chunkOffset:
                    chunk += 1
                    blockCount = 0
                    if len(self.__platforms) <= chunk:
                        self.__platforms.append([])
                if block == 'B':
                    self.__platforms[chunk].append(pygame.Rect(pos_x, pos_y, self.__block_size, self.__block_size))
                if block == 'E':
                    self.enemyGroup.add(Enemy(self, pos_x, pos_y, chunk, self.__enemy_size, self.__enemy_size, 1))
                    enemyCount += 1
                if block == 'C':
                    self.chestGroup.add(Chest(self, self.__game, pos_x, pos_y + (self.__block_size - 40), chunk, self.__chest_size * 1.5, self.__chest_size))
                pos_x = pos_x + self.__block_size
            pos_y = pos_y + self.__block_size  
        logger.info("Created " + str(enemyCount) + " enemie objects")
        

    def update(self,screen):
        """update:
            * renders the blocks on screen and selecting the chunks near by player 
            
            Args:
                * screen (object): pygame screen object
                
            Returns:
                none
                
            Tests:
                * Correct update of world objects
                    
        """
        self.__chunkPlatforms = []                  
        for i in range(-1, 2):
            if self.player.getCurrentChunk() + i >= 0 and self.player.getCurrentChunk() + i < len(self.__platforms):
                self.__chunkPlatforms.extend(self.__platforms[self.player.getCurrentChunk() + i])
        for block in self.__chunkPlatforms:
            screen.blit(self.block_img, (block.x-self.player.getCamOffset(), block.y))
        

    def main(self, screen):
        """main:
            *calling collision and update method and rendering background image

            Args:
                * screen (object): pygame screen object

            Returns:
                none

            Tests:
                * correct rendering position of background image 
                * methods gets called correctly
        """

        self.check_player_collision_bottomblock(self.player.playerPos)
        screen.blit(bg_img, position)
        self.update(screen) 


    def collided_get_y(self, objct_rect, objekt_height):  
        """collided_get_y:
            * returns top coordinate from block, the given "object_rect" (argument) is colliding with.

            Args:
                * objct_rect (object): pygame rect object
                * objekt_height (int): height of the object

            Returns:
                * return_y (int): top coordinate of the block

            Tests:
                * correct return of top coordinate from block while colliding with multiple block objects
                * correct return of -1 if no collision

            Current Bug: 
                * object gets printed on top of block when colliding with the side of block 

        """                        

        return_y = -1
        for block in self.__chunkPlatforms:
            if block.colliderect(objct_rect):
                return_y = block.y - objekt_height           
        return return_y
    

    def check_object_collision_sideblock(self, object_rect):        # Could be coded cleaner with other returns      
        """check_object_collision_sideblock:
            * checks if the given "object_rect" (argument) is colliding with the side of a block
              returns -1 if colliding with the left side of a block and -2 if colliding with the right side of a block 

            Args:
                * object_rect (object): pygame rect object

            Returns: 
                * -1 (int): colliding with the left side of a block
                * -2 (int): colliding with the right side of a block
                * 1 (int): no collision

            Tests:
                * Test if every block in chunkPlatforms gets checked 
                * Test if returns are correct
        """          
        for block in self.__chunkPlatforms:                                    
            #print("block.y: " + str(block.y) + " object_rect.y: " + str(object_rect.y + (object_rect.height)) + " block.height: " + str(block.y + block.height))
            if block.colliderect(object_rect) and block.y < (object_rect.y + object_rect.height -1): #and (object_rect.y + object_rect.height -1) < block.y + block.height: 
                if block.x > object_rect.x:
                    return -1
                elif block.x < object_rect.x:
                    return -2
        return 1   


    def check_player_collision_bottomblock(self, object_rect):
        """check_player_collision_bottomblock:
            * checks if the given "object_rect" (argument) is colliding with the bottom of a block. If collision is detected the y-coordinate of the given object_rect gets set to the bottom of the block.

            Args:
                * object_rect (object): pygame rect object

            Returns: 
                none

            Tests:
                * Test if every block in chunkPlatforms gets checked 
                * Test if y-coordinate of the given object_rect gets set correctly

            """
        
        for block in self.__chunkPlatforms:
            if block.colliderect(object_rect) and self.player.speed_y < 0 and block.y + (block.height/2) < object_rect.y:
                self.player.speed_y = 0
                object_rect.y = block.y + block.height

    
                
                

        
        