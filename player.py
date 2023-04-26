import pygame
from pygame import *
from loguru import logger

class Player(pygame.sprite.Sprite):

    def __init__(self, start_x, start_y, width, height):
        pygame.sprite.Sprite.__init__(self)
       
        self.width = width
        self.height = height
        
        self.idleSprites = []
        self.runRightSprites = []
        self.runLeftSprites = []
        self.jumpSprites = []
        self.shootSprites = []
        self.loadSprites()
    
        self.currentSprite = 0
        self.spriteLoopSpeed = 0.3
        self.image = self.idleSprites[self.currentSprite]
        self.currentAnimation = "idle"
        self.speed_y = 0
        self.speed_x = 0
        self.jump_speed = -11
        self.movement_speed = 8
        self.gravity = 1
        self.latest_shot = 0
        #self.leben = 99

        self.playerPos = pygame.Rect(start_x, start_y, width, height)
        self.rect = self.image.get_rect()
        self.rect.x = self.getCamOffset()
        self.rect.y = start_y
        self.base = pygame.Rect(start_x, start_y + height, width, 2)        #Ground under Player
        self.player_plain = pygame.sprite.RenderPlain(self)

        logger.info("Created player object")

    def loadSprites(self): 
        for i in range(7):
            player_img = pygame.image.load('img/player_img/2_entity_000_IDLE_00' + str(i) + '.png')
            player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))
            self.idleSprites.append(pygame.transform.scale(player_img_cropped, (self.width, self.height)))
        for i in range(7):
            player_img = pygame.image.load('img/player_img/2_entity_000_RUN_00' + str(i) + '.png')
            player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))
            self.runRightSprites.append(pygame.transform.scale(player_img_cropped, (self.width, self.height)))
        for i in range(7):
            player_img = pygame.image.load('img/player_img/2_entity_000_RUN_00' + str(i) + '.png')
            player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))
            self.runLeftSprites.append(pygame.transform.flip(pygame.transform.scale(player_img_cropped, (self.width, self.height)),True, False))
        for i in range(7):
            player_img = pygame.image.load('img/player_img/2_entity_000_JUMP_00' + str(i) + '.png')
            player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))
            self.jumpSprites.append(pygame.transform.scale(player_img_cropped, (self.width, self.height)))
        for i in range(7):
            player_img = pygame.image.load('img/player_img/2_entity_000_ATTACK_00' + str(i) + '.png')
            player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))
            self.shootSprites.append(pygame.transform.scale(player_img_cropped, (self.width, self.height)))    


    def getCamOffset(self):
        return self.playerPos.x - 300                                          #Player in the middle of the screen

    def setWorld(self, world):
        self.world = world

    def main(self, screen):
        self.movement()                                                                                                
        self.move_y()
        self.animation(screen)
            

    def animation(self, screen):
        if self.currentAnimation == "idle":
            self.image = self.idleSprites[int(self.currentSprite)] #self.image = pygame.transform.scale(pygame.image.load('img/player_img/test_idle.png'), (40, 60))
        if self.currentAnimation == "runRight":
            self.image = self.runRightSprites[int(self.currentSprite)]    
        if self.currentAnimation == "runLeft":
            self.image = self.runLeftSprites[int(self.currentSprite)]
        if self.currentAnimation == "jump":
            self.image = self.jumpSprites[int(self.currentSprite)]   
        if self.currentAnimation == "shoot":
            self.image = self.shootSprites[int(self.currentSprite)]
        self.player_plain.draw(screen)

    def move_y(self):
        collided_y = self.world.collided_get_y(self.base)
        if self.speed_y < 0 or collided_y < 0 or (self.world.check_player_collision_sideblock(self.playerPos) != 1 and self.playerPos.y < 600):            
            self.playerPos.y = self.playerPos.y + self.speed_y    
            self.speed_y = self.speed_y + self.gravity
        if self.speed_y >= 0 and collided_y > 0 :#and self.world.check_player_collision_sideblock(self.playerPos) == 1:                  Wenn ELIF Dann in Zeile drüber:       (self.world.check_player_collision_sideblock(self.playerPos) != 1 and self.playerPos.y < 600) and BERÜHRE KEINEN ANDEREN BLOCK IN EBENE UNTER dem Block der Seitlich kollidiert               
            self.playerPos.y = collided_y                                                                                                          #+5 damit der Player nicht über Block schwebt
            self.speed_y = 0        
        self.base.y = self.playerPos.y + self.playerPos.height                                                                    
        self.rect.y = self.playerPos.y 

    def movement(self):
        """Handles the movement of the player
        MOVEMENT BASIERT AUF BUCH ... BUCH ANGEBEN 
        """
        key_state = pygame.key.get_pressed()
        key_down_event_list = pygame.event.get(KEYDOWN)
        if len(key_down_event_list)==0:
            self.speed_x = 0   
            if self.latest_shot + 1000 < pygame.time.get_ticks(): 
                if self.world.collided_get_y(self.base) >= 0:      
                    self.currentAnimation = "idle"
                else:
                    self.currentAnimation = "jump"
        if key_state[K_d] and self.world.check_player_collision_sideblock(self.playerPos) != -1:
            self.speed_x = self.movement_speed
            self.currentAnimation = "runRight"
        if key_state[K_a] and self.world.check_player_collision_sideblock(self.playerPos) != -2:
            if self.playerPos.x > 0:
                self.speed_x = self.movement_speed * -1 
                self.currentAnimation = "runLeft"
        if key_state[K_w]:
            self.jump(self.jump_speed)
            self.currentAnimation = "jump"
        if key_state[K_SPACE]:
            self.shoot()
            self.currentAnimation = "shoot"
        self.currentSprite += self.spriteLoopSpeed           #aus Vid (angeben in Docstring)
        if self.currentSprite >= len(self.idleSprites):
                self.currentSprite = 0
        self.playerPos.x = self.playerPos.x + self.speed_x
        self.base.x = self.playerPos.x         
        self.rect.x = self.playerPos.x - self.getCamOffset()  

    def jump(self, speed):
        if self.world.collided_get_y(self.base)>0 and self.speed_y == 0: 
            self.currentSprite = 0
            self.speed_y = speed    

    def shoot(self):
        self.currentSprite = 3
        self.latest_shot = pygame.time.get_ticks()
        print(self.latest_shot)      
                          
          
    
        