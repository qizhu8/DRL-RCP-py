"""
This class simulates the channel. 

Channel Model:
    We model Channel as a drop tail queue that adds random delay to each incoming packet. 
    Delay is added to the packet when it leaves the queue (to simulate the queue delay).
    If queue is full, drop the packet would like to be added. 

    Delay is an non-negative integer in unit micro second.

    1. Single Mode -> Class SingleModeChannel 
        The added packet delay subjects to a truncated random distribution, e.g. trunket gaussian, poisson, uniform distribution.
        
        Params: 
            processRate: at most how many packets can the channel process per tick
            mode: str "trunket gaussian", "poisson", and "uniform" (case insensitive)
            param: dict
                None: no additional delay
                "trunket gaussian": {min: <min>, max: <max>, mean: <mean>, var: <variance>}
                "poisson":  {min: [0 or customized], max: ["inf" or customized], mean: <mean of possion>}
                "uniform":  {min: <min>, max: <max>}
            queue_size: int  if >= 1, finite queue, otherwise, infinite queue
         
    2. Hidden Markov Mode -> Class MarkoveChannel (Not implement yet. Seems to be not useful)
        The channel changes among each input modes following a discrete Markov process.

        Params: 
            modes: list of N modes
            param: list of parameters of each mode
            init_prob: vector containing the initial probability of N modes
            trans_prob: a N x N matrix storing the transition probability. row i col j: from state i to state j
"""
import random

from channelBuffer import ChannelBuffer
from packet import Packet

class SingleModeChannel(object):
    """
    docstring
    """

    @classmethod
    def parseQueueSize(cls, bufferSize):
        assert isinstance(bufferSize, int), "bufferSize should be an integer"
        
        if bufferSize < 0:
            return -1
        return bufferSize
    
    @classmethod
    def parseProcessRate(cls, processRate):
        assert isinstance(processRate, int) and processRate > 0, "processRate must be a positive integer"
        return processRate

    def ifKeepThePkt(self):
        if random.uniform(0, 1) < self.pktDropProb:
            return False
        
        return True 

    def __init__(self, processRate=1, rtt=0, bufferSize=0, pktDropProb=0, verbose=False):
        self.pktDropProb = pktDropProb
        
        self.bufferSize = self.parseQueueSize(bufferSize)
        self.processRate = self.parseProcessRate(processRate)

        self.verbose = verbose

        self.time = 0
        
        self.rtt = rtt

        # initialize buffer
        self._initBuffer()


    """
    buffer related function
    """
    def _initBuffer(self):
        """
        initialize the buffer
        """
        self.channelBuffer = ChannelBuffer(self.bufferSize, rtt=self.rtt)

    def getLog(self):
        return self.channelBuffer.getLog()
    

    def isFull(self):
        return self.channelBuffer.isFull()
    
    def isEmpty(self):
        return self.channelBuffer.isEmpty()

    """
    channel operations
    """
    def putPackets(self, packetList):
        self.time += 1

        NACKPacketList = []
        pktsDropped_loss = 0
        pktDrop_fullQueue = 0
        dropPidList_loss = []
        dropPidList_fullQueue = []

        for packet in packetList:
            if self.ifKeepThePkt():
                flag = self.channelBuffer.enqueue(packet, time=self.time)
                if not flag:
                    pktDrop_fullQueue += 1
                    dropPidList_fullQueue.append("{suid}-{pid}".format(suid=packet.suid, pid=packet.pid))

                    # generate NACK packet inplace
                    NACKPacketList.append(self._genNACKFromPkt(packet))

            else:
                pktsDropped_loss += 1
                dropPidList_loss.append("{suid}-{pid}".format(suid=packet.suid, pid=packet.pid))
                
                # generate NACK packet inplace
                NACKPacketList.append(self._genNACKFromPkt(packet))

        if self.verbose:
            if pktsDropped_loss:
                print("[-] Channel: {} loss {}".format(pktsDropped_loss, dropPidList_loss))
            if pktDrop_fullQueue:
                print("[-] Channel: {} drop {}".format(pktDrop_fullQueue, dropPidList_fullQueue))
        
        return NACKPacketList

    def _genNACKFromPkt(self, pkt):
        pkt.suid, pkt.duid = pkt.duid, pkt.suid
        pkt.packetType = Packet.NACK
        return pkt

    def getPackets(self):
        packetList = []
        for _ in range(self.processRate):
            flag, _packet = self.channelBuffer.dequeue(self.time)
            if not flag:
                break
            packetList.append(_packet)

        return packetList
    
    def setProcessRate(self, processRate):
        self.processRate = self.parseProcessRate(processRate)

    
    """
    buffer profile
    """
    def profile(self):
        """briefing each user's packet in queue"""
        return self.channelBuffer.getProfile()
    
    def printProfile(self):
        print(self.channelBuffer)



if __name__ == "__main__":
    channel = SingleModeChannel(processRate=1, rtt=100, bufferSize=300)

