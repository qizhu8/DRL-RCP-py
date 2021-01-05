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

    def __init__(self, clientId, serverId, timeout=3, param={"period":3, "pktsPerPeriod": 4, "offset": 0}, verbose=False):
        
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

        self.rttHat = timeout / 3

        self.pktLossTrackingNum = 100
        self.pktLossHat = 0.0
        self.pktLostNum = 0
        self.pktLossInfoQueue = np.zeros(self.pktLossTrackingNum) # keep track of the most recent 100 packets
        self.pktLossInfoPtr = 0

        self.alphaFairness_alpha = 0.9  # shape of alpha-fairness function
        self.alphaFairness_beta = 4     # emphasis on pktLoss rather than delivery time
    
    def _RTTUpdate(self, rtt):
        """this function uses auto-regression to estimate RTT """
        print("\t\t\t rtt ", rtt)
        self.rttHat = self.rttHat * 0.9 + rtt * 0.1
    
    def _pktLossUpdate(self, isLost):
        if self.pktLossInfoQueue[self.pktLossInfoPtr] != isLost:
            self.pktLostNum -= self.pktLossInfoQueue[self.pktLossInfoPtr]
            self.pktLostNum += 1 if isLost else 0
        
        self.pktLossInfoPtr = (self.pktLossInfoPtr+1) % len(self.pktLossInfoQueue)

        self.pktLossHat = self.pktLostNum / self.pktLossTrackingNum

    def calcReward(self, retensionTime):
        def alphaFairness(alpha, x):
            if alpha == 1: return np.log(x)
            return x**(1-alpha) / (1-alpha)
        
        if retensionTime > 0:
            return -self.alphaFairness_beta * alphaFairness(self.alphaFairness_alpha, self.pktLossHat) + alphaFairness(self.alphaFairness_alpha, retensionTime)
        else:
            # retensionTime < 0 means we manually ignore the packet
            return -self.alphaFairness_beta * alphaFairness(self.alphaFairness_alpha, self.pktLossHat)

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

        self.RL_Brain.learn()

        return len(packetList) > 0, packetList
    
    def _handleACK(self, ACKPacketList):
        # process acked packets
        # remove pkts from buffer for those whom ACKs are received
        packetList = []

        for packet in ACKPacketList:
            if packet.duid == self.clientId:
                pid = packet.pid
                if pid not in self.pktsNACKed_SACK:
                    # this packet was falsely claimed to be lost, but was just delayed
                    continue
                print("\t\t\tpkt {} sent at {} received at {}".format(pid, packet.txTime, self.time))
                rtt = self.time - self.pktsNACKed_SACK[pid].txTime
                self._RTTUpdate(rtt)
                self._pktLossUpdate(isLost=False)
                
                # 
                retensionTime = self.time - self.pktsNACKed_SACK[pid].initTxTime
                reward = self.calcReward(retensionTime)
                
                prevState = [
                    self.pktsNACKed_SACK[pid].txAttempts-1, # transmission attempts while making decision
                    self.pktsNACKed_SACK[pid].txTime-self.pktsNACKed_SACK[pid].initTxTime, # retension time when being retransmitted
                    self.pktsNACKed_SACK[pid].rttHat,    # previous rttHat
                    self.pktsNACKed_SACK[pid].pktLossHat,    # previous pktLossHat
                ]
                curState = [
                    self.pktsNACKed_SACK[pid].txAttempts,
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

                # remove the information related to current packet
                self.pktsNACKed_SACK.pop(pid, None)

        self.setTimeout(self.rttHat * 2) 
        # check whether there is a packet needs retransmission
        # retransmit NACKed packets
        
        pidList = list(self.pktsNACKed_SACK) # work around Err "dictionary changed size during iteration"
        for pid in pidList:
            flyingTime = self.time - self.pktsNACKed_SACK[pid].txTime
            if flyingTime >= self.timeout:
                # claim the packet to be lost
                self._pktLossUpdate(isLost=True)
                # decide whether to retransmit 
                curState = [
                    self.pktsNACKed_SACK[pid].txAttempts, # retransmission attempts
                    self.time - self.pktsNACKed_SACK[pid].initTxTime, # retension time
                    self.rttHat,
                    self.pktLossHat
                ]
                action = self.RL_Brain.chooseAction(curState)
                print("action for pkt {} is {}".format(pid, action))
                if action == 1: # retransmit
                    print("[+] retransmit", pid)

                    self.pktsNACKed_SACK[pid].txTime = self.time  # waiting timer clear
                    self.pktsNACKed_SACK[pid].txAttempts += 1 # transmission attempt +1
                    packetList.append(Packet(
                        pid=pid, 
                        suid=self.clientId,
                        duid=self.serverId,
                        txTime=self.time,
                        initTxTime=self.pktsNACKed_SACK[pid].initTxTime,
                        packetType=Packet.MSG))
                else: # ignore
                    print("[-] ignore", pid)

                    reward = self.calcReward(-1)
                    self.RL_Brain.storeExperience(
                        s=curState,a=0,r=reward,s_=curState
                    )
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