"""PIRATE GAME

    Module name: 
            object.py

    Doc:
            This module contains the bullet and chest class.
            Responsible for bullet movement/collision detection and chest logic.

    Classes:
            pygame.sprite.Sprite(builtins.object)
            Bullet

        author: Leon von Detten
        date: 19.04.2023
        version: 1.0.0
        license: free

"""


import pygame
from pygame import *
from loguru import logger



class Bullet(pygame.sprite.Sprite):
    """Bullet:
        * create and instantiate bullet object
        * handle bullet movement
        * handle bullet/__world collision 

    Args:
        pygame.sprite.Sprite (class): simple base class for visible game objects from pygame

    Returns:
        none

    """

    __speed = 20        #bullet speed


    def __init__(self, start_x, start_y, width, height, direction, world):#DOCString ARGS WEITER MACHEN
        """__init__(constructor):
            * Initialize bullet object

        Args:
            * start_x (int): x position of bullet
            * start_y (int): y position of bullet
            * width (int): width of bullet
            * height (int): height of bullet
            * direction (int): direction of bullet
            * world (object): world object
            
        Returns:
            none

        Tests:
            * Correct initialization of bullet object
                - correct start position
                - correct direction

        """

        pygame.sprite.Sprite.__init__(self) 

        self.__direction = direction
        self.__world = world

        self.image = pygame.transform.scale(pygame.image.load("img/bullet_img/bullet.png"), (width, height))
        self.bulletPos = pygame.Rect(start_x, start_y, width, height)
        self.rect = self.image.get_rect()
        self.rect.x = start_x
        self.rect.y = start_y
        
        logger.info("Created bullet object")


    def update(self):
        """update:
            *calls collision, movement and checkFlightDistance methods

            Args:
                none

            Returns:
                none

            Tests:
                * Test if all methods are called
                * Test if methods are called with correct parameters

        """

        self.collision() 
        self.movement()   
        self.checkFlightDistance()
        
        
    def collision(self):
        """collision:
            * checks if bullet collides with block and kills bullet if true

            Args:
                none

            Returns:
                none

            Tests:
                * Test if bullet is killed if collision with block is true
                * Test if bullet is not killed if collision with block is false

            """
        
        if self.__world.check_object_collision_sideblock(self.bulletPos) != 1:      #check if bullet collides with block
            self.kill()                                                             #destroy bullet if true
            logger.info("Bullet collided with block. Got destroyed")


    def checkFlightDistance(self):
        """checkFlightDistance:
            * checks if bullet flew to long (in relation to the player position) and kills bullet if true

            Args:
                none

            Retruns:
                none
            
            Tests:
                * Test if bullet is killed if it flew to long
                * Test if bullet is still in pygame sprite group after flying to long
            
        """

        if self.bulletPos.x > self.__world.player.playerPos.x + 1220 or self.bulletPos.x < self.__world.player.playerPos.x - 1000:  #check if bullet flew to long
            self.kill()                                                                                                             #destroy bullet if true
            logger.info("Bullet flew to long. Got destroyed")        
    
    
    def movement(self):
        """movement:
            * constantly moves bullet in given direction

            Args:
                none

            Returns:
                none

            Tests:
                * Test if bullet is moved in correct direction
                * Test if bullet is moved with correct speed

        """

        self.bulletPos.x += self.__direction * self.__speed         #move bullet in given direction with given speed
        self.rect.x = self.bulletPos.x - self.__world.player.getCamOffset() #update bullet position on screen




class Chest(pygame.sprite.Sprite):
    """Chest:
        * create and instantiate chest object
        * doing chest animation
        * handle collision between player and chestobject

    Args:
        pygame.sprite.Sprite (class): simple base class for visible game objects from pygame

    Returns:
        none

    """
    
    def __init__(self, world, game, position_x, position_y, chunk, width, height):
        """__init__(constructor):
            * Initialize chest object

        Args:
            * world (object): world object
            * game (object): game object
            * position_x (int): x position of chest
            * position_y (int): y position of chest
            * chunk (int): chunk in which the chest is spawned
            * width (int): width of chest
            * height (int): height of chest
            
        Returns:
            none

        Tests:
            * Correct initialization of chest object
                - correct position
                - correct width and height
            * loadSprites method is called

        """

        self.__game = game

        self.__spriteLoopSpeed = 0.2

        self.__chunk = chunk    #area in which the chest is spawned
        self.width = width
        self.height = height
        self.__world = world

        pygame.sprite.Sprite.__init__(self)

        self.__currentSprite = 0    #current sprite of chest animation
        self.__chestSprites = []    #list of all chest sprites
        self.loadSprites()

        self.__gotOpened = False    
        self.__openingStarted = False

        self.image = self.__chestSprites[self.__currentSprite]
        self.chestPos = pygame.Rect(position_x, position_y, width, height)
        self.rect = self.image.get_rect()
        self.rect.x = position_x
        self.rect.y = position_y

        logger.info("Created chest object")


    def update(self):
        """update:
            * calls collision and animation methods

            Args:
                none

            Returns:
                none

            Tests:
                * Test if all methods are called
                * Test if methods are called with correct parameters

        """
        self.collision()
        self.rect.x = self.chestPos.x - self.__world.player.getCamOffset() #update chest position on screen

    
    def loadSprites(self):
        """loadSprites:
            * preloads all chest sprites and scales them to given width and height

            Args:
                none

            Returns:
                none

            Tests:
                * Test if every sprite is loaded and append correctly
                * Test if all sprites are scaled to given width and height

        """

        start_time= pygame.time.get_ticks() #start time for performance measurement
        for i in range(10):                 #iterate through all chest sprites
            self.__chestSprites.append(pygame.transform.scale(pygame.image.load("img/chest_img/chest1_" + str(i) + ".png"), (self.width, self.height))) #load and scale chest sprites
        logger.info("Loaded chest sprites in " + str(pygame.time.get_ticks() - start_time) + "ms")  #log performance
        

    def collision(self):
        """collision:
            * checks if player collides with chest and calls animation method if true

            Args:
                none

            Returns:
                none

            Tests:
                * Test if animation method is called if player collides with chest
                * Test if animation method is not called if player does not collide with chest
                * Test if current sprite is set to 0 if player doesn't collide with chest anymore

        """

        if self.__gotOpened:
            return

        # One touch is enough to trigger the win flow.
        if not self.__openingStarted and self.__world.player.playerPos.colliderect(self.chestPos):
            self.__openingStarted = True
            if hasattr(self.__world.player, "set_frozen"):
                self.__world.player.set_frozen(True)
            # RL sessions can opt into immediate win on first chest touch.
            if hasattr(self.__game, "on_chest_touch") and callable(self.__game.on_chest_touch):
                self.__game.on_chest_touch()
            logger.info("Chest touched. Start opening animation")

        # Continue opening once started, even if player no longer overlaps the chest.
        if self.__openingStarted:
            self.animation()
        self.image = self.__chestSprites[int(self.__currentSprite)]


    def animation(self):
        """animation:
            * Doing chest animation and calls end_game method if animation is finished

            Args:
                none

            Returns:
                none

            Tests:
                * Test if end_game method gets called after whole animation is finished
                * Test if current sprite gets raised

        """

        self.__currentSprite += self.__spriteLoopSpeed  #index of current sprite gets raised
        if (self.__currentSprite >= len(self.__chestSprites) - self.__spriteLoopSpeed):  #index of spirte have to be less than amount of sprites in list - 1 because index starts at 0
            self.__gotOpened = True
            self.__game.end_game()      #call end_game method
            logger.info("Chest got opened. You won!")
            

    def getChunk(self):
        """getChunk:
            * returns chunk in which the chest is located

            Args:
                none

            Returns:
                chunk (int): chunk in which the chest is located

            Tests:
                * Test if correct chunk is returned

        """

        return self.__chunk     #returns current chunk
    
