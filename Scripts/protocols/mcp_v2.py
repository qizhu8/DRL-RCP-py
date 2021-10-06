import numpy as np
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F

from protocols.baseTransportLayerProtocol import BaseTransportLayerProtocol
from RL_Brain import DQN_Brain
from Q_Brain import Q_Brain
from packet import Packet, PacketInfo


class MCP(BaseTransportLayerProtocol):
    requiredKeys = {}
    optionalKeys = {"maxTxAttempts":-1, "timeout":-1, "maxPktTxDDL":-1,
    "alpha":2, # shape of utility function
    "beta1":0.9, "beta2":0.1, # beta1: emphasis on delivery, beta2: emphasis on delay
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
        # self.RL_Brain = DQN_Brain(
        #     nActions=2, stateDim=5, 
        #     batchSize=32,           #
        #     memoryCapacity=1e5,     # maximum number of experiences to store
        #     learningRate=1e-2,      #
        #     updateFrequency=100,    # period to replace target network with evaluation network 
        #     epsilon=0.7,            # greedy policy parameter 
        #     eta=0.9,                # reward discount
        #     epsilon_decay=0.7,
        #     convergeLossThresh=0.01,# below which we consider the network as converged
        #     verbose=False
        # )
        self.RL_Brain = Q_Brain(
            nActions=2
        )

        self.learnCounter = 0
        self.learnPeriod = 8 # number of new data before calling learn

        # self.SRTT = 0 # implemented in base class

        self.pktLossTrackingNum = 100
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
        self.perfDict["deliveredPkts"] = 0 # a client side counter
        self.perfDict["receivedACK"] = 0

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
        self._handleACK(ACKPktList)

        # handle timeout packets
        pktsToRetransmit = self._getRetransPkts()
        self.perfDict["retransAttempts"] += len(pktsToRetransmit)

        # fetch new packets based on cwnd and packets in buffer
        newPktList = self._getNewPktsToSend()
        self.perfDict["newPktsSent"] += len(newPktList)

        # print the progress if verbose=True
        if self.verbose:
            self._printProgress(
                retransPkts=pktsToRetransmit,
                newPktList=newPktList
                )
        
        self.pktIgnoredCounter.append(self.perfDict["ignorePkts"])

        return pktsToRetransmit + newPktList


    def _handleACK(self, ACKPktList):
        ACKPidList = []
        for pkt in ACKPktList:
            if pkt.duid == self.suid and pkt.packetType == Packet.ACK:
                if pkt.pid not in self.buffer:
                    continue

                ACKPidList.append(pkt.pid)

                rtt = self.time-self.buffer[pkt.pid].txTime

                self._rttUpdate(rtt)
                self._timeoutUpdate()

        self._handleACK_SACK(SACKPidList=ACKPidList)


    def _handleACK_SACK(self, SACKPidList):
        for pid in SACKPidList:
            
            # one packet is delivered
            delay = self.time-self.buffer[pid].genTime
            self._delayUpdate(delay=delay)
            self._pktLossUpdate(isLost=False)
            self._deliveryRateUpdate(isDelivered=True)
            self.perfDict["deliveredPkts"] += 1


            if self.buffer[pid].txAttempts > 1 or not self.learnRetransmissionOnly:
                reward = self.calcUtility(1, delay, self.alpha, self.beta1, self.beta2)

                # store the ACKed packet info
                self.RL_Brain.digestExperience(
                    prevState=self.buffer[pid].RLState,
                    action=1,
                    reward=reward,
                    curState=[
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

    def _getRetransPkts(self):
        # wipe out packets that exceed maxTxAttempts and/or maxPktTxDDL
        self._cleanWindow()

        # pkts to retransmit
        timeoutPidSet = self._collectTimeoutPkts()

        # generate pkts and update buffer information
        retransPktList = []
        for pid in timeoutPidSet:
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
            
            reward = self.getSysUtil() # ignore a packet results in zero changes of system utility, so getSysUtil
            self.RL_Brain.digestExperience(
                prevState=self.buffer[pid].RLState,
                action=0,
                reward=reward,
                curState=[
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
                alpha=self.alpha,
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

    def clientSidePerf(self, verbose=False):

        # self.perfDict["retranProb"] = self.perfDict["retransAttempts"]/(self.perfDict["ignorePkts_RL"] + self.perfDict["retransAttempts"])
        if verbose:
            for key in self.perfDict:
                print("{key}:{val}".format(key=key, val=self.perfDict[key]))

        return self.perfDict
    
    def reset(self):
        # reset the object
        self.perfDict = BaseTransportLayerProtocol.perfDictDefault
        self.buffer.clear()
        
        return 
    
    def learn(self):
        
        if not self.RL_Brain.isConverge:
            self.RL_Brain.learn()
        else:
            self.learnCounter += 1
            if self.learnCounter >= self.learnPeriod:
                self.learnCounter = 0
                self.RL_Brain.learn()