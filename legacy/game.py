"""PIRATE GAME
    This is a 2D game where the player has to fight against enemies and jump through the world.

    Module name: 
            game.py

    Doc:
            This module contains the game class.
            Responsible for the game logic (game loop) and screen generation. 

    Classes:
            MyGame

        author: Leon von Detten
        date: 19.04.2023
        version: 1.0.0
        license: free

"""


import os
import sys
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame
from loguru import logger

from world import *
from player import *


class MyGame:
    """MyGame:
        * set up screen width and screen height
        * create and instantiate game object
        * setup game caption
        * read level from file

    Args:
        none 

    Returns:
        none

    """

    __WINDOWWIDTH = 1520
    __WINDOWHEIGHT = 800
    level = []


    def __init__(self):
        """__init__(constructor):
            * Initialize game object

        Args:
            none

        Returns:
            none

        Tests:
            * Correct initialization of game object
                - gameFinished is set to False
            * read_level method is called
            
        """
        self.gameFinished = False
        self.read_level()   #call read_level method
        self.__startTime = pygame.time.get_ticks()
        self.__endTime = 0
        self.__timeNeeded = 0

        logger.info("Created game object")


    def create_window(self):
        """create_window:
            * creates window, sets screen caption and screen size

        Args:
            none

        Returns:
            none

        Tests:
            * Screen caption can be set
            * Scrren size is set correctly

        """

        self.screen = pygame.display.set_mode((self.__WINDOWWIDTH, self.__WINDOWHEIGHT))    #create screen with size(__WINDOWWIDTH, __WINDOWHEIGHT)
        pygame.display.set_caption("2D Game")   #set screen caption to 2D Game  
        logger.info("Created window with size: " + str(self.__WINDOWWIDTH) + "x" + str(self.__WINDOWHEIGHT))    #log window creation

    
    def read_level(self):
        """read_level:
            * read the level from the file and append it to the level list
            
        Args:
            none

        Returns:
            none 

        Tests:
            * File can be read
            * Level list is filled correctly
                - correct order 
                - entire file is read out

        """

        datei = open('level_train_04_mixed.txt','r')   #open file
        for zeile in datei:     #read file line by line
            self.level.append(zeile)    #append line to level list
        datei.close()       #close file
        logger.info("Read level from file")    #log level reading


    def end_game(self):
        """end_game:
            * ends the game and prints the needed time in the middle of the screen

        Args:
            none

        Returns:
            none

        Tests:
            * Needed time is calculated correctly
            * Needed time gets printed in the middle of the screen

        """

        self.__endTime = pygame.time.get_ticks()    #save current time into __endTime
        self.__timeNeeded = str(round((self.__endTime - self.__startTime)/1000, 2))     #calculate needed time and save it into __timeNeeded
        logger.info("Game ended after: " + self.__timeNeeded + "s")    #log needed time
        self.winningText = pygame.font.SysFont('Arial', 80).render("You won! Within: " + self.__timeNeeded + "s", False, (255, 255, 0))  #create winning text
        self.textRect = self.winningText.get_rect()    #create rect of winning text
        self.textRect.center = (self.__WINDOWWIDTH / 2, self.__WINDOWHEIGHT / 2)  
        self.gameFinished = True
        

pygame.init()   #initialize pygame
logger.add("game.log")  #create log file

player_spawn_x = 120    #player spawn x coordinate
player_spawn_y = 50     #player spawn y coordinate
block_size = 60     #block size in pixel

my_game = MyGame()  #create game object
my_game.create_window() #create window

clock = pygame.time.Clock() #create clock object

player = Player(player_spawn_x, player_spawn_y, 40, 60) #instanciate player object from class Player
world = World(my_game, block_size, player)  #instanciate world object from class World
player.setWorld(world)  #set world for player object


#----------Main Game Loop----------

while True: 
    for event in pygame.event.get():    #check for events
        if event.type == pygame.QUIT:   #condition for closing the window
            pygame.quit()   #quit pygame
            sys.exit()  #quit program

    if my_game.gameFinished == True:    #if game is finished print winning text
        my_game.screen.blit(my_game.winningText, my_game.textRect)  

    if my_game.gameFinished == False:   #if game is not finished update screen and call main/update methods
        world.main(my_game.screen)      
        player.main()

        for bullet in (player.bulletGroup): #update every bullet
                bullet.update()

        for chest in world.chestGroup:  #update every chest 
            if player.getCurrentChunk() -1 <= chest.getChunk() <= player.getCurrentChunk() + 1:
                chest.update()
        world.chunkEnemyGroup.empty()   #clears the chunkEnemyGroup

        for enemy in world.enemyGroup:  #iterate through every enemy
            if player.getCurrentChunk() -1 <= enemy.getCurrentChunk() <= player.getCurrentChunk() + 1:  #if enemy is near player add it to chunkEnemyGroup
                enemy.update()
                world.chunkEnemyGroup.add(enemy)

        pygame.sprite.groupcollide(player.bulletGroup, world.chunkEnemyGroup, True, True)   #check for collision between bullet and enemy if true delete both            
        pygame.sprite.Group.draw(world.chunkEnemyGroup, my_game.screen) #draw every enemy in chunkEnemyGroup
        pygame.sprite.Group.draw(player.bulletGroup, my_game.screen)    #draw every bullet
        pygame.sprite.Group.draw(world.chestGroup, my_game.screen) # draw every chest. Only one chest but pygame Group for easier future implementation (multiple chestsv for loot)
        player.player_plain.draw(my_game.screen)    #draw player
        clock.tick(30)  #set fps to 30

    pygame.display.update() #update screen

    #TODOs for future versions:
    #   - add more levels
    #   - save and display best times
    #   - add Menu for start/end game, select level or pause game
 