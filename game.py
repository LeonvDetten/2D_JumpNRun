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
        logger.info("Created game object")
        self.read_level()
        

    def create_window(self):
        """
    Tests:
        * Screen can be created
        * Scrren size can be set
        """
        self.screen = pygame.display.set_mode((self.__WINDOWWIDTH, self.__WINDOWHEIGHT))
        pygame.display.set_caption("2D Game")
        logger.info("Created window with size: " + str(self.__WINDOWWIDTH) + "x" + str(self.__WINDOWHEIGHT))

    
    def read_level(self):
        datei = open('level.txt','r')
        for zeile in datei:
            self.level.append(zeile)
        print(self.level)
        datei.close()



pygame.init()
logger.add("game.log")

player_spawn_x = 120
player_spawn_y = 50
block_size = 60

my_game = MyGame()
my_game.create_window()

clock = pygame.time.Clock()

player = Player(player_spawn_x, player_spawn_y, 40, 60)
world = World(my_game.level, block_size, player)
player.setWorld(world)


while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    #start_time= pygame.time.get_ticks()wd
    world.main(my_game.screen)      #AB HIER GUT KOMMENTIEREN
    player.main()
    for bullet in (player.bulletGroup):
            bullet.update()
    for chest in world.chestGroup:
        if player.getCurrentChunk() -1 <= chest.getChunk() <= player.getCurrentChunk() + 1:
            chest.update()
    world.chunkEnemyGroup.empty()
    for enemy in world.enemyGroup:
        if player.getCurrentChunk() -1 <= enemy.getCurrentChunk() <= player.getCurrentChunk() + 1:
            enemy.update()
            world.chunkEnemyGroup.add(enemy)
    pygame.sprite.groupcollide(player.bulletGroup, world.chunkEnemyGroup, True, True)         
    pygame.sprite.Group.draw(world.chunkEnemyGroup, my_game.screen)
    pygame.sprite.Group.draw(player.bulletGroup, my_game.screen)  
    pygame.sprite.Group.draw(world.chestGroup, my_game.screen) 
    player.player_plain.draw(my_game.screen)
    pygame.display.update()
    clock.tick(30)

    #logger.info("Time for Iteration: " + str(pygame.time.get_ticks() - start_time) + "ms")  #Mit Modulo 1000 stichprobenaertig loggen
    #TODOS in Functions als Comments schreiben (Kanten Fixen (an die Wand springen und oben auf dem Block landen), Nach Schuss folgende animation nicht durchlaufen lassen, wenn Eingabe nur kurz gedrückt)

    #Was soll ich alles loggen (Performance, Keyboard Interaktion, alles?(Wenn Gegner stirbt)) alles lieber zu viel als zu wenig 
    #Wann Abgabe nach Pitch noch Veränderung vornehmen? eine Woche nach Klausuren 

    #Startmenu einabauen
    #Alte Bilder, die durch neue Bilder überlagert werden löschen sonst verwendet Pygame viel Speicher
    #Punkte System einbauen
    #Bestzeiten messen und persitnent speichernw