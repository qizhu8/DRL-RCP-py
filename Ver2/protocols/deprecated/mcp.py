import numpy as np

from protocols.baseTransportLayerProtocol import BaseTransportLayerProtocol
from RL_Brain import DQN
from packet import Packet, PacketInfo

class MCP(BaseTransportLayerProtocol):
    requiredKeys = {}
    optionalKeys = {"maxTxAttempts":-1, "timeout":30, "maxPktTxDDL":-1,
    "beta1":1, "beta2":1, "alpha":0.1, # alpha-fairness beta1: emphasis on delivery, beta2: emphasis on delay
    "gamma":0.9 
    }

    def __init__(self, suid, duid, params, txBufferLen=-1, verbose=False):
        super(MCP, self).__init__(suid=suid, duid=duid, params={}, txBufferLen=txBufferLen, verbose=verbose)

        self.protocolName="MCP"
        self.cwnd = 0
        self.maxTxAttempts = 0
        self.timeout = 0
        

        # ACKMode
        self.ACKMode = "SACK"
        self.pktInfo_dict = {}
        self.numPktsFlying = 0
        # # LC param
        # self.pid_LC = -1
        
        self.verbose = verbose

        self.time = -1


        # RL related variables
        self.RL_Brain = DQN(nActions=2, nStates=5)
        self.rttHat = 0
        self.avgDelay = 0

        self.pktLossTrackingNum = 1000
        self.pktLossHat = 0.0
        self.pktLostNum = 0
        self.pktLossInfoQueue = np.zeros(self.pktLossTrackingNum) # keep track of the most recent 100 packets
        self.pktLossInfoPtr = 0

        # performance collection
        self.distinctPktsSent = 0

        # ACKMode
        self.ACKMode = ""
        self.pktInfo_dict = {}

        self.parseParamByMode(params=params, requiredKeys=MCP.requiredKeys, optionalKeys=MCP.optionalKeys)

    def ticking(self, ACKPktList=[]):
        self.time += 1 
        
        NACKPktList = []

        # process ACK and NACK packets
        NACKPktList += self._handleACK(ACKPktList)

        # handle timeout packets
        NACKPktList += self._collectTimeoutPkts()

        # filter out pkts exceeds maxRetentionTime, maxTxAttempts
        NACKPktList = self._filterOutPktsExceedRetentionTimeAndTxAttempts(NACKPktList)

        # use DRL to decide which packet to retransmit
        self._selectPktToRetrans(NACKPktList)

        # generate new packets
        newPktList, retransPktList = self._getPktsToSend()

        # print the progress if verbose=True
        if self.verbose:
            self._printProgress(
                retransPkts=retransPktList,
                newPktList=newPktList
                )

        return retransPktList + newPktList
    

    def _getPktsToSend(self):
        newPktList = []
        retransPktList = []

        
        numOfNewPackets = len(self.txBuffer) # transmit all packets in buffer

        for _ in range(numOfNewPackets):
            pkt = self.txBuffer.popleft()
            pkt.txTime = self.time

            # TODO: change the variable name to "distincPktsSent"
            if pkt.pid not in self.pktInfo_dict:
                self.distincPktsSent += 1


            if pkt.pid in self.pktInfo_dict:
                self.pktInfo_dict[pkt.pid].txTime = self.time
                self.pktInfo_dict[pkt.pid].isFlying = True
                self.pktInfo_dict[pkt.pid].RLState = [
                    self.pktInfo_dict[pkt.pid].txAttempts,
                    self.time - self.pktInfo_dict[pkt.pid].genTime,
                    self.rttHat,
                    self.pktLossHat,
                    len(self.txBuffer)
                ]
                self.pktInfo_dict[pkt.pid].txAttempts += 1

                retransPktList.append(pkt)
            else:
                self.pktInfo_dict[pkt.pid] = self._genNewPktInfoFromPkt(pkt)
                newPktList.append(pkt)
        
        return newPktList, retransPktList


    def _genNewPktInfoFromPkt(self, pkt):
        pktInfo = PacketInfo(
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
                    self.rttHat,
                    self.pktLossHat,
                    len(self.txBuffer)
                ]
            )

        return pktInfo


    def _handleACK(self, ACKPktList):

        NACKList, ACKList = [], []
        for pkt in ACKPktList:
            if pkt.duid != self.suid:
                continue
            if pkt.pid not in self.pktInfo_dict:
                continue
            if pkt.packetType == Packet.ACK:
                ACKList.append(pkt)
            elif pkt.packetType == Packet.NACK:
                NACKList.append(pkt.pid)

        # self._handleNACK(NACKList)
        self._handleACK_SACK(ACKList)

        return NACKList


    def _handleACK_SACK(self, ACKPktList):
        for pkt in ACKPktList:
            if pkt.pid in self.pktInfo_dict:
                if self.pktInfo_dict[pkt.pid].isFlying:
                    self.numPktsFlying -= 1

                    delay = self.time-self.pktInfo_dict[pkt.pid].genTime
                    rtt = self.time-self.pktInfo_dict[pkt.pid].txTime
                    self._delayUpdate(delay=delay)
                    self._rttUpdate(rtt=rtt)
                    self._pktLossUpdate(isLost=False)

                    reward = self.calcReward(isDelivered=True, retentionTime=delay)

                    # store the ACKed packet info
                    self.RL_Brain.storeExperience(
                        s=self.pktInfo_dict[pkt.pid].RLState,
                        a=1,
                        r=reward,
                        s_=[
                            self.pktInfo_dict[pkt.pid].txAttempts,
                            delay,
                            self.rttHat,
                            self.pktLossHat,
                            len(self.txBuffer)
                        ]
                    )
                    self.RL_Brain.learn()

                self.pktInfo_dict.pop(pkt.pid, None)

    
    def _collectTimeoutPkts(self):
        pidsToCheck = list(self.pktInfo_dict.keys())
        pidsToCheck.sort(reverse=True)

        timoutPktList = []
        for pid in pidsToCheck:
            timoutPktList += self._filterOutTimeoutPkt(pid)
        
        return timoutPktList
    

    def _filterOutTimeoutPkt(self, pid):
        if self._isPktTimeout(pid):
            return [pid]

        return []


    def _filterOutPktsExceedRetentionTimeAndTxAttempts(self, NACKPktList):
        
        NACKPktList = list(set(NACKPktList))
        NACKPktList.sort()

        NACKPktList_filtered = []

        for pid in NACKPktList:
            if pid not in self.pktInfo_dict:
                continue
            if self._isExceedMaxTxAttempts(pid) or self._isExceedMaxRetentionTime(pid):
                if self._isPktFlying(pid):
                    self.numPktsFlying -= 1

                    self._pktLossUpdate(isLost=True)
                    delay = self.time - self.pktInfo_dict[pid].genTime

                    reward = self.calcReward(isDelivered=False, retentionTime=delay)

                    curState = [
                        self.pktInfo_dict[pid].txAttempts,
                        delay,
                        self.rttHat,
                        self.pktLossHat,
                        len(self.txBuffer)
                    ]

                    self.RL_Brain.storeExperience(
                        s=self.pktInfo_dict[pid].RLState,
                        a=1, 
                        r=reward,
                        s_=curState
                    )
                    self.RL_Brain.learn()
                
                self.pktInfo_dict.pop(pid, None)
            else:
                NACKPktList_filtered.append(pid)
        
        return NACKPktList_filtered


    def _selectPktToRetrans(self, pktList):
        for pid in pktList:
            curState = self._getPktCurrentState(pid)

            action = self.RL_Brain.chooseAction(curState)
            if action == 0:
                # packet is ignored
                reward = self.calcReward(isDelivered=False, retentionTime=self.time - self.pktInfo_dict[pid].genTime)
                newState = [
                    self.pktInfo_dict[pid].txAttempts,
                    self.time - self.pktInfo_dict[pid].genTime,
                    self.rttHat,
                    self.pktLossHat,
                    len(self.txBuffer)
                ]
                self.RL_Brain.storeExperience(
                    s=curState,
                    a=0,
                    r=reward,
                    s_=newState
                )

            else: # decide to retransmit the packet
                # self.pktInfo_dict[pid] # no need to update state, will be updated once being retransmitted
                self.txBuffer.appendleft(self.pktInfo_dict[pid].toPacket())



    """RL related functions"""
    
    def calcReward(self, isDelivered, retentionTime):

        r = self.calcUtility(
                deliveryRate=isDelivered,
                avgDelay=retentionTime, 
                alpha=self.alpha, 
                beta1=self.beta1, 
                beta2=self.beta2, 
                deliveredPkts=1)

        return r
    
    def _delayUpdate(self, delay):
        """auto-regression to estimate averaged delay. only for performance check."""
        self.avgDelay = 0.99 * self.avgDelay + 0.01 * delay

    # def _rttUpdate(self, rtt):
    #     """this function uses auto-regression to estimate RTT """
    #     # print("\t\t\t rtt ", rtt)
    #     self.rttHat = self.rttHat * 0.99 + rtt * 0.01
    
    def _pktLossUpdate(self, isLost):
        isLost = int(isLost)
        self.pktLostNum -= self.pktLossInfoQueue[self.pktLossInfoPtr]
        self.pktLostNum += isLost
        self.pktLossInfoQueue[self.pktLossInfoPtr] = isLost
        
        self.pktLossInfoPtr = (self.pktLossInfoPtr+1) % self.pktLossTrackingNum

        self.pktLossHat = self.pktLostNum / self.pktLossTrackingNum

    def _getPktCurrentState(self, pid):
        return [
            self.pktInfo_dict[pid].txAttempts,
            self.time - self.pktInfo_dict[pid].genTime,
            self.rttHat,
            self.pktLossHat,
            len(self.txBuffer)
        ]

    
