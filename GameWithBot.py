import torch
from pirate_game_env import PirateGameEnv
from rl_agent import load_model, run_agent_in_game

if __name__ == "__main__":
    # Initialize the game environment
    env = PirateGameEnv()

    # Load the trained model
    trained_model = load_model("dqn_model.pth", env.observation_space.shape[0], env.action_space.n)

    # Run the bot in the game environment
    run_agent_in_game(env, trained_model)
