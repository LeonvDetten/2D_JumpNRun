import gymnasium as gym
from gymnasium import spaces
import numpy as np

class PirateGameEnv(gym.Env):
    """Custom Environment for Pirate Game compatible with OpenAI Gym"""

    def __init__(self):
        super(PirateGameEnv, self).__init__()

        # Define action space: 4 actions (move left, move right, jump, shoot)
        self.action_space = spaces.Discrete(4)

        # Define observation space: Include player position, enemy positions, and obstacles
        self.observation_space = spaces.Box(
            low=np.array([0, 0, 0, 0]),  # Example: Min values for player position, enemy positions, obstacles
            high=np.array([1520, 800, 10, 10]),  # Example: Max values for player position, enemy positions, obstacles
            dtype=np.float32
        )

        # Initialize game state
        self.state = np.array([0, 0, 0, 0], dtype=np.float32)  # Example: Initial state
        self.done = False

    def step(self, action):
        """Execute one time step within the environment."""
        # Update game state based on action
        if action == 0:  # Move left
            self.state[0] = max(0, self.state[0] - 10)  # Update player x position
        elif action == 1:  # Move right
            self.state[0] = min(1520, self.state[0] + 10)  # Update player x position
        elif action == 2:  # Jump
            self.state[1] = min(800, self.state[1] + 50)  # Update player y position
        elif action == 3:  # Shoot
            self.state[2] += 1  # Example: Increment bullets shot

        # Refined reward logic
        reward = 0
        if self.state[0] >= 1520:  # Reward for reaching the far right
            reward += 100
        # Remove irrelevant rewards for shooting bullets

        # Check if the game is over
        self.done = self._check_done()

        # Return state, reward, done, and additional info
        return self.state, reward, self.done, {}

    def reset(self):
        """Reset the state of the environment to an initial state."""
        # Reset state to initial values
        self.state = np.array([120, 50, 0, 0], dtype=np.float32)  # Example: Reset player position and other state variables
        self.done = False
        return self.state

    def render(self, mode="human"):
        """Render the environment (optional)."""
        import pygame

        if not hasattr(self, 'screen'):
            pygame.init()
            self.screen = pygame.display.set_mode((800, 600))
            pygame.display.set_caption("Pirate Game")

        self.screen.fill((0, 0, 0))  # Schwarzer Hintergrund

        # Beispiel: Zeichne den Spieler als Rechteck
        player_x, player_y = self.state[0], self.state[1]
        pygame.draw.rect(self.screen, (255, 0, 0), (player_x, player_y, 50, 50))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()

    def close(self):
        """Close the environment (optional)."""
        pass

    def _check_done(self):
        """Check if the game is over."""
        # Game ends when the player reaches the far right of the map
        return self.state[0] >= 1520
