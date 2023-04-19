import os
import sys
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame
from loguru import logger
import time

from world import *
from player import *


class MyGame:
    __WINDOWWIDTH = 1520
    __WINDOWHEIGHT = 800
    level = [
             "                                       ",
             "                                         ",
             "                                         ",
             "                                       ",
             "                                         ",
             "                                            ",
             "                                           ",
             "                                            ",
             "                                                 ",
             "                                            ",
             "                                            ",
             "                                            ",
             "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"]

    def __init__(self):
        logger.info("Created game object")
        

    def create_window(self):
        self.screen = pygame.display.set_mode((self.__WINDOWWIDTH, self.__WINDOWHEIGHT))
        pygame.display.set_caption("2D Game")

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

my_game = MyGame()
my_game.create_window()

my_colors = Color()

clock = pygame.time.Clock()

player = Player(player_spawn_x, player_spawn_y, 40, 60)
world = World(my_game.level, 60, my_colors.GREEN, player)
player.setWorld(world)




while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    world.main(my_game.screen)
    player.main(my_game.screen)
    pygame.display.update()
    clock.tick(30)