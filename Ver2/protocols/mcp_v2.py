import numpy as np
import logging

import torch
import torch.nn as nn
import torch.nn.functional as F

from protocols.baseTransportLayerProtocol import BaseTransportLayerProtocol
from RL_Brain import DQN
from packet import Packet, PacketInfo


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


class MCP(BaseTransportLayerProtocol):
    requiredKeys = {}
    optionalKeys = {"maxTxAttempts":-1, "timeout":30, "maxPktTxDDL":-1,
    "beta1":1, "beta2":1, "alpha":0.1, # alpha-fairness beta1: emphasis on delivery, beta2: emphasis on delay
    "gamma":0.9 
    }

    def __init__(self, suid, duid, params, txBufferLen=-1, verbose=False):
        super(MCP, self).__init__(suid=suid, duid=duid, params={}, txBufferLen=txBufferLen, verbose=verbose)

        if verbose:
            logLevel = logging.DEBUG
        else:
            logLevel = logging.WARNING

        logging.basicConfig(
            format="%(asctime)s %(name)s:%(levelname)s:%(message)s", 
            level=logLevel,
            handlers=[
                logging.FileHandler("host-"+str(self.suid)+".log"),
                logging.StreamHandler()
            ])
        
        self.protocolName="MCP"
        self.cwnd = 0
        self.maxTxAttempts = 0
        self.timeout = 0
        
        # ACKMode
        self.ACKMode = "SACK"
        self.verbose = verbose
        self.time = -1

        # RL related variables
        self.RL_Brain = DQN(
            nActions=2, nStates=4, 
            evalNet=DQNNet(nActions=2, nStates=4),
            tgtNet=DQNNet(nActions=2, nStates=4),
            batchSize=64,           #
            memoryCapacity=1e5,     # maximum number of experiences to store
            learningRate=1e-6,      #
            updateFrequency=100,    # period to replace target network with evaluation network 
            epsilon=0.95,           # greedy policy parameter 
            gamma=0.9,              # reward discount
            weight_decay=0.995,
            verbose=False
        )
        # self.SRTT = 0 # implemented in base class
        self.avgDelay = 0

        self.pktLossTrackingNum = 100
        self.pktLossHat = 0.0
        self.pktLostNum = 0
        self.pktLossInfoQueue = np.zeros(self.pktLossTrackingNum) # keep track of the most recent 100 packets
        self.pktLossInfoPtr = 0

        # performance collection
        self.retransPkts_RL = 0
        self.ignorePkts_RL = 0 # ignored by RL
        self.ignorePkts = 0 # also include pkts exceeds txAttempts and retention ddl

        self.parseParamByMode(params=params, requiredKeys=MCP.requiredKeys, optionalKeys=MCP.optionalKeys)

        # initialize the congestion window 
        self.buffer = {}

    def ticking(self, ACKPktList=[]):
        self.time += 1

        # process ACK packets
        NACKPidList = self._handleACK(ACKPktList)

        # fetch new packets based on cwnd and packets in buffer
        newPktList = self._getNewPktsToSend()

        # handle timeout packets
        pktsToRetransmit = self._getRetransPkts(NACKPidList=NACKPidList)

        

        # print the progress if verbose=True
        if self.verbose:
            self._printProgress(
                retransPkts=pktsToRetransmit,
                newPktList=newPktList
                )

        return pktsToRetransmit + newPktList



    def _handleACK(self, ACKPktList):
        NACKPidList, ACKPidList = [], []
        for pkt in ACKPktList:
            if pkt.duid != self.suid:
                continue
            if pkt.packetType == Packet.ACK:
                # note that, this packet may be a redundante SACK
                # for a retransmitted packet.
                # the prev packet is received, but delayed. Therefore,
                # pid may not in buffer
                ACKPidList.append(pkt.pid)

                rtt = self.time-pkt.txTime
                self._rttUpdate(rtt)
                self._timeoutUpdate()

            elif pkt.packetType == Packet.NACK:
                NACKPidList.append(pkt.pid)

        self._handleACK_SACK(SACKPidList=ACKPidList)

        return NACKPidList



    def _handleACK_SACK(self, SACKPidList):
        for pid in SACKPidList:
            if pid in self.buffer:
                # one packet is delivered
                delay = self.time-self.buffer[pid].genTime
                self._delayUpdate(delay=delay)
                self._pktLossUpdate(isLost=False)

                reward = self.calcReward(isDelivered=True, retentionTime=delay)
                # reward_prev = self.calcReward(isDelivered=False, retentionTime=self.buffer[pid].RLState[1])
                # rewardDiff = reward - reward_prev
                rewardDiff = reward
                # store the ACKed packet info
                self.RL_Brain.storeExperience(
                    s=self.buffer[pid].RLState,
                    a=1,
                    r=rewardDiff,
                    s_=[
                        self.buffer[pid].txAttempts,
                        delay,
                        self.SRTT,
                        self.pktLossHat,
                    ]
                )
                self.buffer.pop(pid, None)
                self.RL_Brain.learn()


    def _getNewPktsToSend(self):
        """transmit all packets in txBuffer"""
        self.distincPktsSent += len(self.txBuffer)
        newPktList = [] 

        for _ in range(len(self.txBuffer)):
            newpkt = self.txBuffer.popleft()

            newpkt.txTime = self.time
            newpkt.initTxTime = self.time

            self.addNewPktAndUpdateMemory(newpkt)

            newPktList.append(newpkt)
        
        return newPktList




    def _getRetransPkts(self, NACKPidList=[]):
        # wipe out packets that exceed maxTxAttempts and/or maxPktTxDDL
        self._cleanWindow()
        
        # clean NACK list without considering pkts wiped out in _cleanWindow
        retransPidSet = set(self.buffer.keys()) & set(NACKPidList)

        # collect timeout packets
        timeoutPidSet = set(self._collectTimeoutPkts())

        # pkts to retransmit
        retransPidSet |= timeoutPidSet

        # generate pkts and update buffer information
        retransPktList = []
        for pid in retransPidSet:

            # use RL to make a decision
            curState = [
                self.buffer[pid].txAttempts,
                self.time - self.buffer[pid].genTime,
                self.SRTT,
                self.pktLossHat,
            ]
            action = self.RL_Brain.chooseAction(state=curState)

            if action == 0:
                # ignored
                self.ignorePkts_RL += 1
                self.ignorePktAndUpdateMemory(pid, popKey=True)
            else:
                self.retransPkts_RL += 1

                retransPktList.append(self.buffer[pid].toPacket())
                
                self.buffer[pid].txAttempts += 1
                self.buffer[pid].txTime = self.time
                self.buffer[pid].RLState = [
                    self.buffer[pid].txAttempts,
                    self.time - self.buffer[pid].genTime,
                    self.SRTT,
                    self.pktLossHat,
                ]

        return retransPktList


    def _cleanWindow(self):
        if self.maxTxAttempts > -1:
            pktsToConsider = set(self.buffer.keys())
            for pid in pktsToConsider:
                if self.buffer[pid].txAttempts >= self.maxTxAttempts:
                    self.ignorePktAndUpdateMemory(pid, popKey=True)

        if self.maxPktTxDDL > -1:
            pktsToConsider = set(self.buffer.keys())
            timeDDL = self.time - self.maxPktTxDDL
            for pid in pktsToConsider:
                if self.buffer[pid].genTime < timeDDL:
                    self.ignorePktAndUpdateMemory(pid, popKey=True)
        return

    def ignorePktAndUpdateMemory(self, pid, popKey=True):
        self.ignorePkts += 1
        if pid in self.buffer:
            delay = self.time - self.buffer[pid].genTime
            reward = self.calcReward(isDelivered=False, retentionTime=delay)
            # reward_prev = self.calcReward(isDelivered=False, retentionTime=self.buffer[pid].RLState[1])
            # rewardDiff = reward - reward_prev
            rewardDiff = reward
            self.RL_Brain.storeExperience(
                s=self.buffer[pid].RLState,
                a=0,
                r=rewardDiff,
                s_=[
                    self.buffer[pid].txAttempts,
                    delay,
                    self.SRTT,
                    self.pktLossHat,
                ]
            )
            self.RL_Brain.learn()

        if popKey:
            self.buffer.pop(pid, None)

        return
    
    def addNewPktAndUpdateMemory(self, pkt):
        self.buffer[pkt.pid] = PacketInfo(
            pid=pkt.pid, 
            suid=pkt.suid, 
            duid=pkt.duid,
            txTime=pkt.txTime,
            genTime=pkt.genTime,
            initTxTime=pkt.txTime, 
            txAttempts=1,
            isFlying=True,
            RLState=[
                    0, # txAttempt BEFORE taking the action
                    self.time - pkt.genTime,
                    self.SRTT,
                    self.pktLossHat,
                ])


    def _collectTimeoutPkts(self):
        timoutPidList = []
        for pid in self.buffer:
            timeDDL = self.time - self.timeout
            if self.buffer[pid].txTime < timeDDL:
                timoutPidList.append(pid)
        
        return timoutPidList


    """RL related functions"""
    
    def calcReward(self, isDelivered, retentionTime):

        r = self.calcUtility(
                deliveryRate=isDelivered+0,
                avgDelay=retentionTime, 
                alpha=self.alpha, 
                beta1=self.beta1, 
                beta2=self.beta2, 
                deliveredPkts=1)

        return r
    
    def _delayUpdate(self, delay):
        """auto-regression to estimate averaged delay. only for performance check."""
        self.avgDelay = 0.99 * self.avgDelay + 0.01 * delay
    
    def _pktLossUpdate(self, isLost):
        isLost = int(isLost)
        self.pktLostNum -= self.pktLossInfoQueue[self.pktLossInfoPtr]
        self.pktLostNum += isLost
        self.pktLossInfoQueue[self.pktLossInfoPtr] = isLost
        
        self.pktLossInfoPtr = (self.pktLossInfoPtr+1) % self.pktLossTrackingNum

        self.pktLossHat = self.pktLostNum / self.pktLossTrackingNum

    
