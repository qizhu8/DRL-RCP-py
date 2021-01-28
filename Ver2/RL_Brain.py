"""
As the filename, this script implement an Reinforment Learning brain.
"""
import sys
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from collections import deque

class DQN(object):

    def __init__(self, 
        nStates,                # dimension of the system state
        nActions,               # dimension of the action space
        evalNet,
        tgtNet,
        batchSize=64,           #
        memoryCapacity=1e5,     # maximum number of experiences to store
        learningRate=1e-6,      #
        updateFrequency=100,     # period to replace target network with evaluation network 
        epsilon=0.95,            # greedy policy parameter
        turnOffGreedyLoss=1,  # turn off greedy policy when loss is below than
        gamma=0.9,              # reward discount
        deviceStr="cpu",         # primary computing device cpu or cuda
        weight_decay=0.995,
        verbose=False,
        ):

        self.nActions = nActions
        self.nStates = nStates

        # create eval net and target net
        self.evalNet = evalNet
        self.tgtNet = tgtNet

        # selection of optimizer and loss function
        # self.optimizer = torch.optim.Adam(self.evalNet.parameters(), lr=learningRate)
        # self.optimizer = torch.optim.RMSprop(self.evalNet.parameters(), lr=learningRate)
        self.optimizer = torch.optim.SGD(self.evalNet.parameters(), lr=learningRate, weight_decay=weight_decay)

        # self.lr_scheduler = torch.optim.lr_scheduler.ExponentialLR(optimizer=self.optimizer, gamma=0.99) # decay lr


        self.lossFunc = nn.MSELoss()
        self.loss = sys.maxsize
        self.divergeCounter = sys.maxsize # if self.divergeCounter > 3, turn on Greedy because of bad perf
        self.convergeCounter = 0

        self.batchSize = batchSize
        self.learningCounter = 0 # learning steps before updating tgtNet
        self.updateFrequencyFinal = updateFrequency # how often to update the network parameter
        self.updateFrequencyCur = self.updateFrequencyFinal/2

        self.memoryCounter = 0  # experience pieces
        self.memoryCapacity = int(memoryCapacity)
        self.memory = np.zeros((self.memoryCapacity, nStates*2+2)) # storing [curState, action, reward, nextState], so nStates*2 + 2

        # other input parameters
        self.epsilon = epsilon
        self.turnOffGreedyLoss = turnOffGreedyLoss
        self.globalEvalOn = False # True: ignore greedy random policy
        self.isConverge = False # whether the network meets the converge
        self.gamma = gamma
        self.updateFrequency = updateFrequency

        self.device = torch.device(deviceStr)

        self.verbose = verbose

        


    def chooseAction(self, state, evalOn=False):
        state = torch.unsqueeze(torch.FloatTensor(state), 0) # to vector

        # epsilon greedy
        if evalOn or self.globalEvalOn or np.random.uniform() < self.epsilon:
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

        # use the history state, history action, reward, and the ground truth new state
        # to train a regression network that predicts the reward correct.
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

        self.loss = loss.cpu().detach().numpy()
        if self.verbose and self.learningCounter == 1:
            # self.lr_scheduler.step() # decay learning rate
            print("loss=", self.loss)

        if loss < self.turnOffGreedyLoss:
            self.isConverge = True
        
        if loss > 20*self.turnOffGreedyLoss:
            self.isConverge = False

        # if not self.globalEvalOn and loss < self.turnOffGreedyLoss:
        #     self.convergeCounter += 1
        #     self.divergeCounter = 0
        #     if self.convergeCounter > 3:
        #         if self.verbose:
        #             print("[+] turn off greedy: loss {loss} < {threshold}".format(loss=self.loss, threshold=self.turnOffGreedyLoss))
        #         self.isConverge = True
        #         self.globalEvalOn = True
        
        # if self.globalEvalOn and loss > 20*self.turnOffGreedyLoss:
        #     self.convergeCounter = 0
        #     self.divergeCounter += 1
        #     if self.divergeCounter > 3: # three consecutive bad performance
        #         if self.verbose:
        #             print("[-] turn on greedy: loss {loss} > {threshold}".format(loss=self.loss, threshold=20*self.turnOffGreedyLoss))
        #         self.isConverge = False
        #         self.globalEvalOn = False

        

        # back propagation
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()