"""
use gym to test our RL_Brain.py
"""

import gym
import numpy as np

from RL_Brain import DQN

# environment
env = gym.make('CartPole-v0')
env = env.unwrapped

nActions = env.action_space.n 
nStates = env.observation_space.shape[0]

dqn = DQN(nStates=nStates, nActions=nActions)

for i_episode in range(400):
    state = env.reset() # initial state
    ep_r = 0
    while True:
        env.render()
        action = dqn.chooseAction(state, randomOnly=dqn.memoryCounter < dqn.batchSize)

        # take action
        newState, reward, done, info = env.step(action)

        # compute reward based on system states
        x, x_dot, theta, theta_dot = newState
        r1 = (env.x_threshold - abs(x)) / env.x_threshold - 0.8
        r2 = (env.theta_threshold_radians - abs(theta)) / env.theta_threshold_radians - 0.5
        r = r1 + r2

        # store transition
        dqn.storeExperience(state, action, r, newState)

        ep_r += r
        # learn only when there are enough experiences to sample from
        # if dqn.memoryCounter > dqn.batchSize:
            # dqn.learn()
        dqn.learn()
        if done:
            print('Ep: ', i_episode, '| Ep_r: ', round(ep_r, 2))

        if done:
            break
        state = newState