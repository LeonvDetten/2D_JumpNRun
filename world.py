import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame

bg_img = pygame.image.load('img/background_img/bg.jpg')
bg_img = pygame.transform.scale(bg_img, (1520, 800))
position = (0, 0)

class World:
    def __init__(self, level, block_size, platform_color):#, player):
        self.level = level
        self.block_size = block_size
        self.platform_color = platform_color
        #self.player = player
        self.platforms = []
        self.posn_x = 0
        self.posn_y = 0

        for line in self.level:
            self.posn_x = 0
            for block in line:
                if block == 'B':
                    self.platforms.append(pygame.Rect(self.posn_x, self.posn_y, block_size, block_size))
                self.posn_x = self.posn_x + block_size
            self.posn_y = self.posn_y + block_size    

    def update(self,screen):
        for block in self.platforms:
            pygame.draw.rect(screen, self.platform_color, pygame.Rect(block.x, block.y, block.width, block.height), 0)

    def main(self, screen):
        screen.blit(bg_img, position)
        self.update(screen)
        