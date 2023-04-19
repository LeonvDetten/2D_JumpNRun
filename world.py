import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
import pygame

bg_img = pygame.image.load('img/background_img/bg.jpg')
bg_img = pygame.transform.scale(bg_img, (1520, 800))
position = (0, 0)

class World:
    def __init__(self, level, block_size, platform_color, player):
        self.level = level
        self.block_size = block_size
        self.platform_color = platform_color
        self.player = player
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
            pygame.draw.rect(screen, self.platform_color, pygame.Rect(block.x-self.player.getCamOffset(), block.y, block.width, block.height), 0)

    def main(self, screen):
        #self.check_player_collision_sideblock(self.player.playerPos) 
        screen.blit(bg_img, position)
        self.update(screen) #evt nicht in Loop wegen Performance

    def collided_get_y(self, player_rect):                          
        return_y = -1
        for block in self.platforms:
            if block.colliderect(player_rect):
                return_y = block.y - block.height + 1
                # if block.y < player_rect.y-1:
                #     print("Block seite!")
                #     print("block.y:" , block.y)
                #     print("player_rect.y:" , player_rect.y-1)
                #     #print("block.y + block.height:" , block.y + block.height)
                
        return return_y
    
    def check_player_collision_sideblock(self, player_rect):                  
        for block in self.platforms:
            if block.colliderect(player_rect) and block.y == (self.player.playerPos.y - 1):     #geht nicht für Sprünge: Intervall machen block_oberkante>player>block_unterkante       
                if block.x > player_rect.x:
                    return -1
                elif block.x < player_rect.x:
                    return -2
        return 1        
        
        