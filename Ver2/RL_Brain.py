"""
As the filename, this script implement an Reinforment Learning brain.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from collections import deque

class DQNNet(nn.Module):
    """Our decision making network"""
    def __init__(self, nStates, nActions):
        super(DQNNet, self).__init__()
        self.fc1 = nn.Linear(nStates, 20)
        self.fc2 = nn.Linear(20, 50)
        self.fc3 = nn.Linear(50, 20)
        self.out = nn.Linear(20, nActions)
        # self.out = nn.Linear(50, nActions)

        # initialize weights
        self.fc1.weight.data.normal_(0, 1)
        self.fc2.weight.data.normal_(0, 1)
        self.fc3.weight.data.normal_(0, 1)
        self.out.weight.data.normal_(0, 1)
    
    def forward(self, state):
        # layer 1
        x = F.relu(self.fc1(state))
        x = F.relu(self.fc2(x))
        x = F.relu(self.fc3(x))
        # out
        return self.out(x)

class DQN(object):

    def __init__(self, 
        nStates,                # dimension of the system state
        nActions,               # dimension of the action space
        batchSize=64,           #
        memoryCapacity=1e5,     # maximum number of experiences to store
        learningRate=1e-6,      #
        updateFrequency=100,     # period to replace target network with evaluation network 
        epsilon=0.95,            # greedy policy parameter 
        gamma=0.9,              # reward discount
        deviceStr="cpu"         # primary computing device cpu or cuda
        ):

        self.nActions = nActions
        self.nStates = nStates

        # create eval net and target net
        self.evalNet = DQNNet(nStates=nStates, nActions=nActions)
        self.tgtNet = DQNNet(nStates=nStates, nActions=nActions)

        # selection of optimizer and loss function
        # self.optimizer = torch.optim.Adam(self.evalNet.parameters(), lr=learningRate)
        self.optimizer = torch.optim.RMSprop(self.evalNet.parameters(), lr=learningRate)
        self.optimizer = torch.optim.SGD(self.evalNet.parameters(), lr=learningRate, weight_decay=0.995)

        # self.lr_scheduler = torch.optim.lr_scheduler.ExponentialLR(optimizer=self.optimizer, gamma=0.99) # decay lr


        self.lossFunc = nn.MSELoss()

        self.batchSize = batchSize
        self.learningCounter = 0 # learning steps before updating tgtNet
        self.updateFrequencyFinal = updateFrequency # how often to update the network parameter
        self.updateFrequencyCur = self.updateFrequencyFinal/2

        self.memoryCounter = 0  # experience pieces
        self.memoryCapacity = int(memoryCapacity)
        self.memory = np.zeros((self.memoryCapacity, nStates*2+2)) # storing [curState, action, reward, nextState], so nStates*2 + 2

        # other input parameters
        self.epsilon = epsilon
        self.gamma = gamma
        self.updateFrequency = updateFrequency

        self.device = torch.device(deviceStr)


        


    def chooseAction(self, state, evalOn=False):
        state = torch.unsqueeze(torch.FloatTensor(state), 0) # to vector

        # epsilon greedy
        if evalOn or np.random.uniform() < self.epsilon:
            actionRewards = self.evalNet.forward(state) # actionRewards if of shape 1 x nAction
    
            # action = torch.argmax(actionRewards, 1)
            action = torch.max(actionRewards, 1)[1] # the [1] pointed to argmax
            action = action.cpu().data.numpy()[0] # add [0] at last because we want int rather than [int]
        else:
            action = np.random.randint(0, self.nActions)
        return action
    
    def storeExperience(self, s, a, r, s_):
        experience = np.hstack((s, [a, r], s_))
        storageAddr = self.memoryCounter % self.memoryCapacity
        self.memory[storageAddr, :] = experience
        self.memoryCounter += 1
    
    def learn(self):
        # check whether to update tgtNet
        if self.memoryCounter <= 0:
            return

        # if self.learningCounter > self.updateFrequencyCur:
        if self.learningCounter > self.updateFrequencyFinal:
            self.tgtNet.load_state_dict(self.evalNet.state_dict())
            self.learningCounter = 0
            # quick update initially, slow update later
            # self.updateFrequencyCur *= 1.1
            # self.updateFrequencyCur = min(self.updateFrequencyCur, self.updateFrequencyFinal)
        self.learningCounter += 1

        # randomly sample $batch experiences 
        availableExperiences = min(self.memoryCapacity, self.memoryCounter)

        sampleIdxs = np.random.choice(availableExperiences, min(availableExperiences, self.batchSize))
        experiences = self.memory[sampleIdxs, :]

        states = torch.FloatTensor(experiences[:, :self.nStates])
        actions = torch.LongTensor(experiences[:, self.nStates:self.nStates+1].astype(int))
        rewards = torch.FloatTensor(experiences[:, self.nStates+1:self.nStates+2])
        nextStates = torch.FloatTensor(experiences[:, -self.nStates:])


        # q value based on evalNet
        curQ = self.evalNet(states).gather(1, actions) # select the maximum reward based on actions
        
        # q value based on the system
        nextQ = self.tgtNet(nextStates).detach() # no gradient needed (detach) <=> no back propagation needed
        # apply Bellman's equation
        tgtQ = rewards + self.gamma * nextQ.max(1)[0].view(-1, 1)
        loss = self.lossFunc(curQ, tgtQ)

        if self.learningCounter == 1:
            # self.lr_scheduler.step() # decay learning rate
            print("loss=", loss)

        # back propagation
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()