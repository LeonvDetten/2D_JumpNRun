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
        self.__platforms = [[]]     # list for platforms
        self.__chunkPlatforms = []  # list for platforms (blocks) in chunks near player

        self.enemyGroup = pygame.sprite.Group()     # pygamegroup for enemies
        self.chunkEnemyGroup = pygame.sprite.Group()        # pygamegroup for enemies in chunks near player
        self.chestGroup = pygame.sprite.Group()     # pygamegroup for chests

        self.block_img = pygame.image.load('img/ground_img/spaceground.png')    # load block image
        self.block_img = pygame.transform.scale(self.block_img, (block_size, block_size))   # scale block image

        self.initializeWorld()
        logger.info("Created world object")


    def initializeWorld(self):
        """initializeWorld:
            * Initialize world objects by iterating through level list

        Args:
            none

        Returns:
            none

        Tests
            * Objects gets appended into pygame sprite groups
            * blocks are in the correct chunk

        Generating Level from list inspired by: 
            https://www.reddit.com/r/pygame/comments/12ideai/level_from_the_list/

        Optimization:
            - numpy vectorized operations (.where) for collision detection

        """

        pos_y = 0   # reset y position for objects
        enemyCount = 0
        for line in self.__level:   # iterate through lines in level list
            pos_x = 0               # reset x position for objects
            blockCount = 0          # reset block count
            chunk = 0               # reset chunk
            for block in line:      # iterate through blocks in line
                blockCount += 1     # increase block count
                if blockCount > self.__chunkOffset:     # check if block count is bigger than chunk offset
                    chunk += 1                          # increase chunk
                    blockCount = 0                      # reset block count
                    if len(self.__platforms) <= chunk:
                        self.__platforms.append([])
                if block == 'B':    # check if B (block) is in current block
                    self.__platforms[chunk].append(pygame.Rect(pos_x, pos_y, self.__block_size, self.__block_size))     # append block to platforms list
                if block == 'E':    # check if E (enemy) is in current block
                    self.enemyGroup.add(Enemy(self, pos_x, pos_y, chunk, self.__enemy_size, self.__enemy_size, 1))      # append enemy to enemy group
                    enemyCount += 1
                if block == 'C':    # check if C (chest) is in current block
                    self.chestGroup.add(Chest(self, self.__game, pos_x, pos_y + (self.__block_size - 40), chunk, self.__chest_size * 1.5, self.__chest_size))   # append chest to chest group
                pos_x = pos_x + self.__block_size   # increase x position by block size
            pos_y = pos_y + self.__block_size       # increase y position by block size
        logger.info("Created " + str(enemyCount) + " enemie objects")
        

    def update(self,screen):
        """update:
            * renders the blocks on screen and selecting the chunks near by player 
            
            Args:
                * screen (object): pygame screen object
                
            Returns:
                none
                
            Tests:
                * Correct update of __chunkPlatforms list
                * Correct blocks are rendered on screen 
                    
        """

        self.__chunkPlatforms = []      # reset chunk platforms list                  
        for i in range(-1, 2):          # iterate through chunks near by player (+-1 chunk)
            if self.player.getCurrentChunk() + i >= 0 and self.player.getCurrentChunk() + i < len(self.__platforms):    # check if chunk is in range of platforms list
                self.__chunkPlatforms.extend(self.__platforms[self.player.getCurrentChunk() + i])                       # appending platforms in chunk near by player to chunk platforms list
        for block in self.__chunkPlatforms: # iterate through chunk platforms list
            screen.blit(self.block_img, (block.x-self.player.getCamOffset(), block.y))      # renders blocks on screen
        

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
        screen.blit(bg_img, position)       # renders background image
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
        for block in self.__chunkPlatforms:     # iterate through chunk platforms list
            if block.colliderect(objct_rect):   # check if object (argument) is colliding with block
                return_y = block.y - objekt_height  
        return return_y     #returns top coordinate of block - object height (needed for the calculation of objects position)
    

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
        for block in self.__chunkPlatforms:     # iterate through chunk platforms list                                    
            if block.colliderect(object_rect) and block.y < (object_rect.y + object_rect.height -1): # check if object (argument) is colliding with block and if object is not above block
                if block.x > object_rect.x:     # check if block is on the right side of object
                    return -1
                elif block.x < object_rect.x:   # check if block is on the left side of object
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
        
        for block in self.__chunkPlatforms:     # iterate through chunk platforms list
            if block.colliderect(object_rect) and self.player.speed_y < 0 and block.y + (block.height/2) < object_rect.y:       # check if object (argument) is colliding with block and if the player is jumping
                self.player.speed_y = 0
                object_rect.y = block.y + block.height

    
                
                

        
        