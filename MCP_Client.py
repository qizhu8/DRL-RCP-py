"""
In this script, we implement the smart client for MCP.

The general behavior is simlar to SimpleClient in Applications, 
but the handling of NACK packet is based on Deep Reinforcement Learning.

For the preliminary version, MCP_Client goes with MCP_Server that gives back 
not only ACK but also NACK (hacked)
"""
import numpy as np

from Applications import SimpleClient
from RL_Brain import DQN
from packet import Packet, PacketInfo


class MCP_Client(SimpleClient):

    def __init__(self, clientId, serverId, timeout=100, param={"period":3, "pktsPerPeriod": 4, "offset": 0}, verbose=False):
        
        SimpleClient.__init__(self, clientId=clientId, serverId=serverId, timeout=timeout, appMode="periodic", param=param, verbose=verbose)
        
        """
        State = [
          "retransmission attempts", 
          "retension time in buffer", 
          "current packet drop rate",
          "current rtt",
        ]
        Action is in [retransmission, drop]
        """

        self.RL_Brain = DQN(nActions=2, nStates=4)
        self.ignoredPkts = 0
        self.retransPkts = 0


        self.rttHat = timeout / 3
        self.avgDelay = 0

        self.pktDeliveryDDL = 100 # no more attempts after 
        self.pktRetransMax = 5    # no more attempts after

        self.pktLossTrackingNum = 1000
        self.pktLossHat = 0.0
        self.pktLostNum = 0
        self.pktLossInfoQueue = np.zeros(self.pktLossTrackingNum) # keep track of the most recent 100 packets
        self.pktLossInfoPtr = 0

        self.alphaFairness_alpha = 0.9  # shape of alpha-fairness function
        self.alphaFairness_beta1 = 4     # emphasis on pktLoss rather than delivery time
        self.alphaFairness_beta2 = 4
    
    def _delayUpdate(self, delay):
        """auto-regression to estimate averaged delay. only for performance check."""
        self.avgDelay = 0.99 * self.avgDelay + 0.01 * delay

    def _RTTUpdate(self, rtt):
        """this function uses auto-regression to estimate RTT """
        # print("\t\t\t rtt ", rtt)
        self.rttHat = self.rttHat * 0.99 + rtt * 0.01
    
    def _pktLossUpdate(self, isLost):
        isLost = int(isLost)
        self.pktLostNum -= self.pktLossInfoQueue[self.pktLossInfoPtr]
        self.pktLostNum += isLost
        self.pktLossInfoQueue[self.pktLossInfoPtr] = isLost

        
        self.pktLossInfoPtr = (self.pktLossInfoPtr+1) % self.pktLossTrackingNum

        self.pktLossHat = self.pktLostNum / self.pktLossTrackingNum

    def calcReward(self, retensionTime):
        def alphaFairness(x):
            if self.alphaFairness_alpha == 1: return np.log(x)
            return x**(1-self.alphaFairness_alpha) / (1-self.alphaFairness_alpha)
        
        return -self.alphaFairness_beta1 * alphaFairness(self.pktLossHat + 1) - self.alphaFairness_beta2 * alphaFairness(retensionTime)


    def ticking(self, ACKPacketList=[], noNewPackets=False):
        """
        client actions in each time slot (tick)
        1. check ACK and decides which packet to retransmit
        2. transmit new packets
        """
        self.time += 1
        packetList = []

        # process ACK
        packetList += self._handleACK(ACKPacketList)

        if self.verbose and packetList:
            print("Client {} retransmits ".format(self.clientId), end="")
            for packet in packetList:
                print(" {}".format(packet.pid), end="")
            print()

        # generate new packets
        # flag, newPacketList = self._transmitNewPacket()
        if not noNewPackets:
            packetList += self._transmitNewPacket()
        

        return len(packetList) > 0, packetList
    
    def _handleACK(self, ACKPacketList):
        # process acked packets
        # remove pkts from buffer for those whom ACKs are received
        packetList = []

        for packet in ACKPacketList:
            if packet.duid == self.clientId:
                pid = packet.pid

                # print("====================txTime=",  packet.txTime)
                rtt = self.time - packet.txTime
                delay = self.time - packet.initTxTime
                self._RTTUpdate(rtt)
                self._pktLossUpdate(isLost=False)
                self._delayUpdate(delay)
                # 
                retensionTime = self.time - packet.initTxTime
                reward = self.calcReward(retensionTime)
                
                prevState = [
                    packet.txAttempts-1, # transmission attempts while making decision
                    packet.txTime-packet.initTxTime, # retension time when being retransmitted
                    packet.rttHat,    # previous rttHat
                    packet.pktLossHat,    # previous pktLossHat
                ]
                curState = [
                    packet.txAttempts,
                    retensionTime,
                    self.rttHat,
                    self.pktLossHat
                ]
                self.RL_Brain.storeExperience(
                    s=prevState,
                    a=1,
                    r=reward,
                    s_=curState
                )
                self.RL_Brain.learn()

                # remove the information related to current packet
                if pid in self.pktsNACKed_SACK:
                    self.pktsNACKed_SACK.pop(pid, None)

        # self.setTimeout(self.rttHat * (1-self.pktLossHat) + self.rttHat * self.pktLossHat*3) 
        # check whether there is a packet needs retransmission
        # retransmit NACKed packets
        
        pidList = list(self.pktsNACKed_SACK) # work around Err "dictionary changed size during iteration"
        for pid in pidList:
            flyingTime = self.time - self.pktsNACKed_SACK[pid].txTime
            if flyingTime >= self.timeout:
                # claim the packet to be lost
                self._pktLossUpdate(isLost=True)

                retensionTime = self.time - self.pktsNACKed_SACK[pid].initTxTime
                toGiveUp = retensionTime > self.pktDeliveryDDL or self.pktsNACKed_SACK[pid].txAttempts > self.pktRetransMax

                # decide whether to retransmit 
                curState = [
                    self.pktsNACKed_SACK[pid].txAttempts, # retransmission attempts
                    self.time - self.pktsNACKed_SACK[pid].initTxTime, # retension time
                    self.rttHat,
                    self.pktLossHat
                ]
                action = self.RL_Brain.chooseAction(curState)
                if not toGiveUp and action == 1: # retransmit
                    # if self.verbose:
                    #     print("[+] retransmit", pid)
                    self.retransPkts += 1
                    self.pktsNACKed_SACK[pid].txTime = self.time  # waiting timer clear
                    self.pktsNACKed_SACK[pid].txAttempts += 1 # transmission attempt +1
                    packetList.append(Packet(
                        pid=pid, 
                        suid=self.clientId,
                        duid=self.serverId,
                        txTime=self.time,
                        initTxTime=self.pktsNACKed_SACK[pid].initTxTime,
                        txAttempts=self.pktsNACKed_SACK[pid].txAttempts,
                        rttHat=self.rttHat,
                        pktLossHat=self.pktLossHat,
                        packetType=Packet.MSG))
                else: # ignore
                    # if self.verbose:
                    #     print("[-] ignore", pid)
                    self._pktLossUpdate(isLost=True)

                    self.ignoredPkts += 1
                    reward = self.calcReward(self.pktDeliveryDDL)
                    self.RL_Brain.storeExperience(
                        s=curState,a=0,r=reward,s_=curState
                    )
                    self.RL_Brain.learn()

                    self.pktsNACKed_SACK.pop(pid, None)
                
        return packetList

    def _transmitNewPacket(self):

        # generate new packets based on the current state
        self.state = (self.state + 1) % self.period

        newPacketList = []
        if self.time > self.trafficOffset:
            if self.state == 0: # send packets at the begining of the period
                if self.verbose:
                    print("Client {} transmits ".format(self.clientId), end="")
                for _ in range(self.pktsPerPeriod):
                    newPacketList.append(Packet(
                        pid=self.pid, 
                        suid=self.clientId,
                        duid=self.serverId,
                        txTime=self.time,
                        initTxTime=self.time,
                        rttHat=self.rttHat,
                        pktLossHat=self.pktLossHat,
                        packetType=Packet.MSG))
                    if self.verbose:
                        print(" {}".format(self.pid), end="")
                    
                    self.pktsNACKed_SACK[self.pid] = PacketInfo(
                        pid=self.pid, suid=self.serverId, duid=self.clientId, txTime=self.time, initTxTime=self.time, txAttempts=1, rttHat=self.rttHat, pktLossHat=self.pktLossHat
                    )
                    self.pid += 1
                if self.verbose:
                    print()
        
        return newPacketList
    
    def printPerf(self):
        print("client {id}: \n Channel State Est: rtt {rtt}, pktLossRate {pktLossRate}".format(
            id=self.clientId,
            rtt=self.rttHat, 
            pktLossRate=self.pktLossHat))
        print("Pkts Ingored:{}, pkts retrans:{}, pkts id:{}".format(self.ignoredPkts, self.retransPkts, self.pid))
        print("avg delay:{}".format(self.avgDelay))