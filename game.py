import os
import sys
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame
from loguru import logger

from world import *
from player import *

class MyGame:
    __WINDOWWIDTH = 1520
    __WINDOWHEIGHT = 800
    level = [
             "              BB           E              ",
             "                                         ",
             "    B           BBB                          ",
             "                       EEEEE                           B",
             "    E                          BBBBBBBBBBBBBBBB           ",
             "                          BBBB                  ",
             " B                   BBBBB                       ",
             "                  BBBB                          ",
             "    EEE           BBBB            E                     ",
             "            BBB    BBB                       E    ",
             "         BBBB            BBB    E                  ",
             " BB                         B      BBBBBBB              ",
             "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"]

    def __init__(self):
        logger.info("Created game object")
        

    def create_window(self):
        self.screen = pygame.display.set_mode((self.__WINDOWWIDTH, self.__WINDOWHEIGHT))
        pygame.display.set_caption("2D Game")
        logger.info("Created window with size: " + str(self.__WINDOWWIDTH) + "x" + str(self.__WINDOWHEIGHT))

class Color():
        WHITE = (255, 255, 255)
        BLACK = (0, 0, 0)
        RED = (255, 0, 0)
        GREEN = (0, 255, 0)
        BLUE = (0, 0, 255)

pygame.init()
logger.add("game.log")

player_spawn_x = 120
player_spawn_y = 100
block_size = 60

my_game = MyGame()
my_game.create_window()

my_colors = Color()

clock = pygame.time.Clock()

player = Player(player_spawn_x, player_spawn_y, 40, 60)
world = World(my_game.level, block_size, my_colors.GREEN, player)
player.setWorld(world)

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    start_time= pygame.time.get_ticks()
    world.main(my_game.screen)
    player.main(my_game.screen)
    for bullet in (player.bulletGroup):
            bullet.update()
    for enemy in (world.enemyGroup):
            enemy.update()
    pygame.sprite.groupcollide(player.bulletGroup, world.enemyGroup, True, True)        
    pygame.sprite.Group.draw(player.bulletGroup, my_game.screen)    
    pygame.sprite.Group.draw(world.enemyGroup, my_game.screen)
    pygame.display.update()
    clock.tick(30)

    logger.info("Time for Iteration: " + str(pygame.time.get_ticks() - start_time) + "ms")
    #TODOS in Functions als Comments schreiben (bsp.jumpleft jump right anstatt jump allgemein, Kanten Fixen (an die Wand springen und oben auf dem Block landen), Durch Block buggen wenn er blockietrt und man Springt, collisionsfeinheiten(links von Block abstand zwischen Block und Spieler))