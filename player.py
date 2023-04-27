import pygame
from pygame import *
from loguru import logger

from object import *

class Player(pygame.sprite.Sprite):

    def __init__(self, start_x, start_y, width, height):
        pygame.sprite.Sprite.__init__(self)
       
        self.width = width
        self.height = height
        
        self.idleRightSprites = []
        self.idleLeftSprites = []
        self.runRightSprites = []
        self.runLeftSprites = []
        self.jumpRightSprites = []
        self.jumpLeftSprites = []
        self.shootRightSprites = []
        self.shootLeftSprites = []
        self.loadSprites()
    
        self.currentSprite = 0
        self.spriteLoopSpeed = 0.3
        self.image = self.idleRightSprites[self.currentSprite]
        self.currentAnimation = "idle"
        self.speed_y = 0
        self.speed_x = 0
        self.jump_speed = -10
        self.movement_speed = 8
        self.latest_shot = 0
        self.shootAnimationTime = 1000
        self.direction = 1
        #self.leben = 99

        self.playerPos = pygame.Rect(start_x, start_y, width, height)
        self.rect = self.image.get_rect()
        self.rect.x = self.getCamOffset()
        self.rect.y = start_y
        self.base = pygame.Rect(start_x, start_y + height, width, 2)        #Ground under Player
        self.player_plain = pygame.sprite.RenderPlain(self)

        self.bulletGroup = pygame.sprite.Group()

        logger.info("Created player object")

    def loadSprites(self): 
        start_time= pygame.time.get_ticks()
        for image in range(7):
            player_img = pygame.image.load('img/player_img/2_entity_000_IDLE_00' + str(image) + '.png')
            player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))
            self.idleRightSprites.append(pygame.transform.scale(player_img_cropped, (self.width, self.height)))
        for image in range(7):
            player_img = pygame.image.load('img/player_img/2_entity_000_IDLE_00' + str(image) + '.png')
            player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))
            self.idleLeftSprites.append(pygame.transform.flip(pygame.transform.scale(player_img_cropped, (self.width, self.height)),True, False))    
        for image in range(7):
            player_img = pygame.image.load('img/player_img/2_entity_000_RUN_00' + str(image) + '.png')
            player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))
            self.runRightSprites.append(pygame.transform.scale(player_img_cropped, (self.width, self.height)))
        for image in range(7):
            player_img = pygame.image.load('img/player_img/2_entity_000_RUN_00' + str(image) + '.png')
            player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))
            self.runLeftSprites.append(pygame.transform.flip(pygame.transform.scale(player_img_cropped, (self.width, self.height)),True, False))
        for image in range(7):
            player_img = pygame.image.load('img/player_img/2_entity_000_JUMP_00' + str(image) + '.png')
            player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))
            self.jumpRightSprites.append(pygame.transform.scale(player_img_cropped, (self.width, self.height)))
        for image in range(7):
            player_img = pygame.image.load('img/player_img/2_entity_000_JUMP_00' + str(image) + '.png')
            player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))
            self.jumpLeftSprites.append(pygame.transform.flip(pygame.transform.scale(player_img_cropped, (self.width, self.height)),True, False))    
        for image in range(7):
            player_img = pygame.image.load('img/player_img/2_entity_000_ATTACK_00' + str(image) + '.png')
            player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))
            self.shootRightSprites.append(pygame.transform.scale(player_img_cropped, (self.width, self.height)))   
        for image in range(7):
            player_img = pygame.image.load('img/player_img/2_entity_000_ATTACK_00' + str(image) + '.png')
            player_img_cropped = player_img.subsurface(pygame.Rect(200, 250, 825, 850))
            self.shootLeftSprites.append(pygame.transform.flip(pygame.transform.scale(player_img_cropped, (self.width, self.height)),True, False))     
        logger.info("Loaded player sprites in " + str(pygame.time.get_ticks() - start_time) + "ms")

    def getCamOffset(self):
        return self.playerPos.x - 300                                          #Player in the middle of the screen

    def setWorld(self, world):
        self.world = world

    def main(self, screen):
        self.movement()                                                                                                
        self.move_y()
        self.animation(screen)         

    def animation(self, screen):
        if self.currentAnimation == "idleRight":
            self.image = self.idleRightSprites[int(self.currentSprite)] 
        if self.currentAnimation == "idleLeft":
            self.image = self.idleLeftSprites[int(self.currentSprite)]
        if self.currentAnimation == "runRight":
            self.image = self.runRightSprites[int(self.currentSprite)]    
        if self.currentAnimation == "runLeft":
            self.image = self.runLeftSprites[int(self.currentSprite)]
        if self.currentAnimation == "jumpRight":
            self.image = self.jumpRightSprites[int(self.currentSprite)]  
        if self.currentAnimation == "jumpLeft":
            self.image = self.jumpLeftSprites[int(self.currentSprite)]
        if self.currentAnimation == "shootRight":
            self.image = self.shootRightSprites[int(self.currentSprite)]
        if self.currentAnimation == "shootLeft":
            self.image = self.shootLeftSprites[int(self.currentSprite)]
        self.player_plain.draw(screen)

    def move_y(self):
        collided_y = self.world.collided_get_y(self.base, self.height)
        if self.speed_y < 0 or collided_y < 0 or (self.world.check_object_collision_sideblock(self.playerPos) != 1 and self.playerPos.y < 600):            
            self.playerPos.y += self.speed_y    
            self.speed_y += self.world.gravity
        if self.speed_y >= 0 and collided_y > 0 :#and self.world.check_object_collision_sideblock(self.playerPos) == 1:                  
            self.playerPos.y = collided_y                                             
            self.speed_y = 0        
        self.base.y = self.playerPos.y + self.height                                                                    
        self.rect.y = self.playerPos.y 

    def movement(self):
        """Handles the movement of the player
        MOVEMENT BASIERT AUF BUCH ... BUCH ANGEBEN 
        """
        key_state = pygame.key.get_pressed()
        key_down_event_list = pygame.event.get(KEYDOWN)
        if len(key_down_event_list)==0:
            self.speed_x = 0   
            if self.latest_shot + self.shootAnimationTime < pygame.time.get_ticks(): 
                if self.world.collided_get_y(self.base, self.height) >= 0:  
                    if self.direction == -1:                          
                        self.currentAnimation = "idleLeft"
                    else:
                        self.currentAnimation = "idleRight"
                else:
                    if self.direction == -1:
                        self.currentAnimation = "jumpLeft"
                    else:
                        self.currentAnimation = "jumpRight"
        if key_state[K_d] and self.world.check_object_collision_sideblock(self.playerPos) != -1:
            self.speed_x = self.movement_speed
            self.direction = 1
            self.currentAnimation = "runRight"
        if key_state[K_a] and self.world.check_object_collision_sideblock(self.playerPos) != -2:
            if self.playerPos.x > 0:
                self.speed_x = self.movement_speed * -1 
                self.direction = -1
                self.currentAnimation = "runLeft"
        if key_state[K_w]:
            self.jump(self.jump_speed)
        if (key_state[K_SPACE] or key_state[K_RETURN]) and self.latest_shot + self.shootAnimationTime < pygame.time.get_ticks():
            self.shoot()
        self.currentSprite += self.spriteLoopSpeed           #aus Vid (angeben in Docstring)
        if self.currentSprite >= len(self.idleRightSprites):
                self.currentSprite = 0
        self.playerPos.x += self.speed_x
        self.base.x = self.playerPos.x         
        self.rect.x = self.playerPos.x - self.getCamOffset()  

    def jump(self, speed):
        if self.world.collided_get_y(self.base, self.height)>0 and self.speed_y == 0: 
            if self.direction == -1:                          
                self.currentAnimation = "jumpLeft"
            else:
                self.currentAnimation = "jumpRight"
            self.currentSprite = 0
            self.speed_y = speed    

    def shoot(self):
        self.currentSprite = 3
        if self.direction == -1:
            self.currentAnimation = "shootLeft"
        else:
            self.currentAnimation = "shootRight"    
        self.bulletGroup.add(Bullet(self.playerPos.x + (0.8*self.width), self.playerPos.y + (self.height*0.45), 10, 5, self.direction, self.world))
        self.latest_shot = pygame.time.get_ticks()     
    
                          
          
    
        