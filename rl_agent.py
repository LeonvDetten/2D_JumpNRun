import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import matplotlib.pyplot as plt
from pirate_game_env import PirateGameEnv
import time

class DQN(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(DQN, self).__init__()
        self.fc = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, output_dim)
        )

    def forward(self, x):
        return self.fc(x)

def save_model(policy_net, file_path="dqn_model.pth"):
    torch.save(policy_net.state_dict(), file_path)
    print(f"Model saved to {file_path}")

def load_model(file_path="dqn_model.pth", input_dim=None, output_dim=None):
    model = DQN(input_dim, output_dim)
    model.load_state_dict(torch.load(file_path))
    model.eval()
    print(f"Model loaded from {file_path}")
    return model

def evaluate_agent(env, policy_net):
    state = env.reset()
    state = torch.tensor(state, dtype=torch.float32).unsqueeze(0)
    total_reward = 0

    while True:
        with torch.no_grad():
            action = torch.argmax(policy_net(state)).item()

        next_state, reward, done, _ = env.step(action)
        next_state = torch.tensor(next_state, dtype=torch.float32).unsqueeze(0)
        total_reward += reward

        state = next_state

        if done:
            break

    print(f"Evaluation Total Reward: {total_reward}")

def plot_metrics(rewards, epsilons):
    plt.figure(figsize=(12, 5))

    plt.subplot(1, 2, 1)
    plt.plot(rewards)
    plt.title("Total Reward per Episode")
    plt.xlabel("Episode")
    plt.ylabel("Total Reward")

    plt.subplot(1, 2, 2)
    plt.plot(epsilons)
    plt.title("Epsilon Decay")
    plt.xlabel("Episode")
    plt.ylabel("Epsilon")

    plt.tight_layout()
    plt.show()

def train_agent(env, episodes=100, gamma=0.99, epsilon=1.0, epsilon_decay=0.995, min_epsilon=0.01, lr=0.001):
    input_dim = env.observation_space.shape[0]
    output_dim = env.action_space.n

    policy_net = DQN(input_dim, output_dim)
    target_net = DQN(input_dim, output_dim)
    target_net.load_state_dict(policy_net.state_dict())
    target_net.eval()

    optimizer = optim.Adam(policy_net.parameters(), lr=lr)
    criterion = nn.MSELoss()

    replay_buffer = []
    max_buffer_size = 10000
    batch_size = 64

    rewards = []
    epsilons = []

    for episode in range(episodes):
        state = env.reset()
        state = torch.tensor(state, dtype=torch.float32).unsqueeze(0)
        total_reward = 0

        while True:
            if np.random.rand() < epsilon:
                action = env.action_space.sample()
            else:
                with torch.no_grad():
                    action = torch.argmax(policy_net(state)).item()

            next_state, reward, done, _ = env.step(action)
            next_state = torch.tensor(next_state, dtype=torch.float32).unsqueeze(0)
            total_reward += reward

            replay_buffer.append((state, action, reward, next_state, done))
            if len(replay_buffer) > max_buffer_size:
                replay_buffer.pop(0)

            state = next_state

            if len(replay_buffer) >= batch_size:
                indices = np.random.choice(len(replay_buffer), batch_size, replace=False)
                batch = [replay_buffer[i] for i in indices]
                states, actions, rewards_batch, next_states, dones = zip(*batch)

                states = torch.cat(states)
                actions = torch.tensor(actions, dtype=torch.int64).unsqueeze(1)
                rewards_batch = torch.tensor(rewards_batch, dtype=torch.float32).unsqueeze(1)
                next_states = torch.cat(next_states)
                dones = torch.tensor(dones, dtype=torch.float32).unsqueeze(1)

                q_values = policy_net(states).gather(1, actions)
                with torch.no_grad():
                    next_q_values = target_net(next_states).max(1, keepdim=True)[0]
                    target_q_values = rewards_batch + gamma * next_q_values * (1 - dones)

                loss = criterion(q_values, target_q_values)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

            if done:
                break

        rewards.append(total_reward)
        epsilons.append(epsilon)

        epsilon = max(min_epsilon, epsilon * epsilon_decay)

        if episode % 10 == 0:
            target_net.load_state_dict(policy_net.state_dict())

        print(f"Episode {episode}, Total Reward: {total_reward}, Epsilon: {epsilon}")

    save_model(policy_net)
    plot_metrics(rewards, epsilons)

# Example usage for integration into the game
def run_agent_in_game(env, model):
    state = env.reset()
    state = torch.tensor(state, dtype=torch.float32).unsqueeze(0)

    while True:
        env.render()  # Zeigt den aktuellen Zustand des Spiels an

        with torch.no_grad():
            action = torch.argmax(model(state)).item()

        print(f"Action: {action}, State: {state}")  # Debugging-Ausgabe

        next_state, reward, done, _ = env.step(action)
        next_state = torch.tensor(next_state, dtype=torch.float32).unsqueeze(0)

        # Update state
        state = next_state

        time.sleep(0.5)  # Füge einen Delay von 0.5 Sekunden hinzu

        if done:
            print("Game Over")
            break

# Example integration
if __name__ == "__main__":
    env = PirateGameEnv()
    trained_model = load_model("dqn_model.pth", env.observation_space.shape[0], env.action_space.n)
    run_agent_in_game(env, trained_model)
