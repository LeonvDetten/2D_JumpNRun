import os
import sys
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame
from loguru import logger

from world import *

pygame.init()
logger.add("game.log")

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
             "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"]

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


my_game = MyGame()
my_game.create_window()
my_colors = Color()

world = World(my_game.level, 60, my_colors.GREEN)


while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    world.main(my_game.screen)
    pygame.display.update()