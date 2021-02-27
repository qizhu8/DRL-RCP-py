import numpy as np
import sys

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
        # one layer
        # self.fc1 = nn.Linear(nStates, 50)
        # self.out = nn.Linear(50, nActions)

        # self.fc1.weight.data.normal_(0, 1)
        # self.out.weight.data.normal_(0, 1)

        # two layers
        self.fc1 = nn.Linear(nStates, 20)
        self.fc2 = nn.Linear(20, 30)
        self.out = nn.Linear(30, nActions)

        # self.fc1.weight.data.normal_(0, 1)
        # self.fc2.weight.data.normal_(0, 1)
        # self.out.weight.data.normal_(0, 1)
    
    def forward(self, state):
        # one layer
        # x = torch.sigmoid(self.fc1(state))

        # two layers
        x = torch.sigmoid(self.fc1(state))
        x = self.fc2(x)

        return self.out(x)


class MCP(BaseTransportLayerProtocol):
    requiredKeys = {}
    optionalKeys = {"maxTxAttempts":-1, "timeout":30, "maxPktTxDDL":-1,
    "beta1":1, "beta2":1, # beta1: emphasis on delivery, beta2: emphasis on delay
    "gamma":0.9,
    "learnRetransmissionOnly": False
    }

    def __init__(self, suid, duid, params, txBufferLen=-1, verbose=False):
        super(MCP, self).__init__(suid=suid, duid=duid, params={}, txBufferLen=txBufferLen, verbose=verbose)
        
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
            nActions=2, nStates=5, 
            evalNet=DQNNet(nActions=2, nStates=5),
            tgtNet=DQNNet(nActions=2, nStates=5),
            batchSize=32,           #
            memoryCapacity=1e5,     # maximum number of experiences to store
            learningRate=1e-2,      #
            updateFrequency=100,    # period to replace target network with evaluation network 
            epsilon=0.7,            # greedy policy parameter 
            gamma=0.9,              # initial gamma
            weight_decay=1,
            epsilon_decay=0.7,
            turnOffGreedyLoss=0.01,
            verbose=False
        )
        self.learnCounter = 0
        self.learnPeriod = 8 # number of new data before calling learn

        # self.SRTT = 0 # implemented in base class
        # self.perfDict["avgDelay"] = 0

        self.pktLossTrackingNum = 100
        #self.perfDict["pktLossHat"] = 0.0 #
        self.pktLostNum = 0
        self.pktLossInfoQueue = np.zeros(self.pktLossTrackingNum) # keep track of the most recent 100 packets
        self.pktLossInfoPtr = 0

        # performance collection

        self.parseParamByMode(params=params, requiredKeys=MCP.requiredKeys, optionalKeys=MCP.optionalKeys)

        # initialize the congestion window 
        self.buffer = {}

        # override perfDict
        self.perfDict["ignorePkts_RL"] = 0 # pkts ignored by RL
        self.perfDict["ignorePkts"] = 0 # pkts ignored by RL and max tx attempts

        self.perfDict["newPktsSent"] = 0
        self.perfDict["retransAttempts"] = 0
        self.perfDict["retranProb"] = 0
        self.perfDict["pktLossHat"] = 0
        self.perfDict["avgDelay"] = 0
        self.perfDict["deliveryRate"] = 0
        self.perfDict["convergeAt"] = sys.maxsize # when the RL_brain works relatively good (converge)
        self.perfDict["RL_loss"] = sys.maxsize
        self.perfDict["maxWin"] = 0

        # for debug
        self.pktIgnoredCounter = []

    def ticking(self, ACKPktList=[]):
        self.time += 1

        self._RL_lossUpdate(self.RL_Brain.loss)
        self.perfDict["epsilon"] = self.RL_Brain.epsilon
        if self.RL_Brain.isConverge and self.time < self.perfDict["convergeAt"]:
            self.perfDict["convergeAt"] = self.time

        # process ACK packets
        NACKPidList = self._handleACK(ACKPktList)

        # fetch new packets based on cwnd and packets in buffer
        newPktList = self._getNewPktsToSend()
        self.perfDict["newPktsSent"] += len(newPktList)

        # handle timeout packets
        pktsToRetransmit = self._getRetransPkts(NACKPidList=NACKPidList)
        self.perfDict["retransAttempts"] += len(pktsToRetransmit)

        # print the progress if verbose=True
        if self.verbose:
            self._printProgress(
                retransPkts=pktsToRetransmit,
                newPktList=newPktList
                )
        
        self.pktIgnoredCounter.append(self.perfDict["ignorePkts"])

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
                self._deliveryRateUpdate(isDelivered=True)

                if self.buffer[pid].txAttempts > 1 or not self.learnRetransmissionOnly:
                    # reward = curUtil - self.buffer[pid].util

                    curutil = self.calcUtility(1, delay, self.beta1, self.beta2)
            
                    # the expected utility if I gave up the packet
                    # delay_if_gaveup =self.buffer[pid].RLState[1]
                    # potentialUtil = self.calcUtility(0, delay_if_gaveup, self.beta1, self.beta2)
                    # potentialUtil = self.calcUtility(0, 0, self.beta1, self.beta2)
                    curSysUtil = self.getSysUtil()

                    reward = curutil - curSysUtil

                    # store the ACKed packet info
                    self.RL_Brain.storeExperience(
                        s=self.buffer[pid].RLState,
                        a=1,
                        r=reward,
                        s_=[
                            self.buffer[pid].txAttempts,
                            delay,
                            self.SRTT,
                            self.perfDict["pktLossHat"],
                            self.perfDict["avgDelay"]
                        ]
                    )
                    self.learn()

                self.buffer.pop(pid, None)


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
        
        # 
        self.perfDict["maxWin"] = max(self.perfDict["maxWin"], len(self.buffer))
        
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
            # update lost packet estimation 
            self._pktLossUpdate(isLost=True)

            # use RL to make a decision
            curState = [
                self.buffer[pid].txAttempts,
                self.time - self.buffer[pid].genTime,
                self.SRTT,
                self.perfDict["pktLossHat"],
                self.perfDict["avgDelay"]
            ]
            action = self.RL_Brain.chooseAction(state=curState)

            self._RL_retransUpdate(action)

            if action == 0:
                # ignored
                self.perfDict["ignorePkts_RL"] += 1
                self.ignorePktAndUpdateMemory(pid, popKey=True)
            else:
                retransPktList.append(self.buffer[pid].toPacket())
                
                self.buffer[pid].txAttempts += 1
                self.buffer[pid].txTime = self.time
                self.buffer[pid].util = self.getSysUtil()
                self.buffer[pid].RLState = [
                    self.buffer[pid].txAttempts,
                    self.time - self.buffer[pid].genTime,
                    self.SRTT,
                    self.perfDict["pktLossHat"],
                    self.perfDict["avgDelay"]
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
        # if we ignore a packet, even though we harm the delivery rate, but we contribute to delay
        self.perfDict["ignorePkts"] += 1

        # ignore a packet contributes to no delay penalty
        
        self._deliveryRateUpdate(isDelivered=False) # update delivery rate

        if pid in self.buffer:
            delay = self.time - self.buffer[pid].genTime
            # curutil = self.calcUtility(0, delay, self.beta1, self.beta2)
            curutil = self.calcUtility(0, 0, self.beta1, self.beta2)
            
            # the expected utility if I don't do this action
            # potentialUtil = self.calcUtility(1-self.perfDict["pktLossHat"], delay + self.SRTT, self.beta1, self.beta2)
            curSysUtil = self.getSysUtil()
            
            reward = curutil - curSysUtil 
            # reward = self.calcUtility(0, delay, self.beta1, self.beta2)

            self.RL_Brain.storeExperience(
                s=self.buffer[pid].RLState,
                a=0,
                r=reward,
                s_=[
                    self.buffer[pid].txAttempts,
                    delay,
                    self.SRTT,
                    self.perfDict["pktLossHat"],
                    self.perfDict["avgDelay"]
                ]
            )
            self.learn()

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
                    self.perfDict["pktLossHat"],
                    self.perfDict["avgDelay"]
                ])


    def _collectTimeoutPkts(self):
        timoutPidList = []
        for pid in self.buffer:
            timeDDL = self.time - self.timeout
            if self.buffer[pid].txTime < timeDDL:
                timoutPidList.append(pid)
        
        return timoutPidList


    """RL related functions"""
    
    # def calcReward(self, isDelivered, retentionTime):
    def getSysUtil(self, delay=None):
        # get the current system utility

        if not delay:
            delay = self.perfDict["avgDelay"]

        return self.calcUtility(
                deliveryRate=self.perfDict["deliveryRate"],
                avgDelay=delay, 
                beta1=self.beta1, 
                beta2=self.beta2
                )
    
    def _delayUpdate(self, delay, update=True):
        """auto-regression to estimate averaged delay. only for performance check."""
        alpha = 0.01
        if update:
            self.perfDict["avgDelay"] = (1-alpha) * self.perfDict["avgDelay"] + alpha * delay
            return self.perfDict["avgDelay"]
        else:
            return (1-alpha) * self.perfDict["avgDelay"] + alpha * delay


    def _deliveryRateUpdate(self, isDelivered):
        alpha = 0.001
        self.perfDict["deliveryRate"] = (1-alpha) * self.perfDict["deliveryRate"] + alpha * int(isDelivered)

    def _pktLossUpdate(self, isLost):
        # channel state estimate
        isLost = int(isLost)
        self.pktLostNum -= self.pktLossInfoQueue[self.pktLossInfoPtr]
        self.pktLostNum += isLost
        self.pktLossInfoQueue[self.pktLossInfoPtr] = isLost
        
        self.pktLossInfoPtr = (self.pktLossInfoPtr+1) % self.pktLossTrackingNum

        self.perfDict["pktLossHat"] = self.pktLostNum / self.pktLossTrackingNum

    def _RL_lossUpdate(self, loss):
        # keep track of RL network
        self.perfDict["RL_loss"] = (7/8.0) * self.perfDict["RL_loss"] + (1/8.0) * loss

    def _RL_retransUpdate(self, isRetrans):
        self.perfDict["retranProb"] = 0.99 * self.perfDict["retranProb"] + 0.01 * int(isRetrans)

    def clientSidePerf(self):

        # self.perfDict["retranProb"] = self.perfDict["retransAttempts"]/(self.perfDict["ignorePkts_RL"] + self.perfDict["retransAttempts"])
        for key in self.perfDict:
            print("{key}:{val}".format(key=key, val=self.perfDict[key]))

        return self.perfDict
    
    def reset(self):
        # reset the object
        self.perfDict = BaseTransportLayerProtocol.perfDictDefault
        self.buffer.clear()
        
        return 
    
    def learn(self):
        self.learnCounter += 1
        if self.learnCounter >= self.learnPeriod:
            self.learnCounter = 0
            self.RL_Brain.learn()