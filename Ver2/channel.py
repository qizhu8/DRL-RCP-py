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
         
    2. Hidden Markov Mode -> Class MarkoveChannel
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

    supportModes = {None, "gaussian", "poisson", "uniform"}
    gaussianParam = {
        "required": {"mean":10, "var":10}, 
        "optional": {"min":0, "max":-1, "isBounded":False}}
    poissonParam = {
        "required": {"mean":10}, 
        "optional": {"min":0, "max":-1, "isBounded":False}}
    uniformParam = {"required": {"min":0, "max":10},
        "optional": {}}

    @classmethod
    def parseMode(cls, mode):
        """
        verify user's input mode
        """
        if mode:
            assert isinstance(mode, str), "mode should be a string among "+cls.supportModes.__str__()
            mode = mode.lower()
            assert mode in cls.supportModes, "support modes are "+cls.supportModes.__str__()
            return mode
        return mode
    
    @classmethod
    def parseParam(cls, mode, param):
        """
        verify the param
        """
        
        def paramCheck(param, defaultParam, paramTemplate):
            """
            check parameter based on the template
            """
            _param = defaultParam
            # check required keys
            for key in paramTemplate["required"]:
                assert key in param, "key " + key + " is required"
                
                _param[key] = param[key]
            
            # check optional keys
            for key in paramTemplate["optional"]:
                if(key in param):
                    _param[key] = param[key]

            return _param
    
        def checkGaussianParam(cls, param):
            """ """
            _param = {"mean":10, "var":10, "min":0, "max":-1, "isBounded":False}
            _param = paramCheck(param, _param, cls.gaussianParam)
            
            # check min max
            if _param["isBounded"]:
                assert _param["max"] >= _param["min"], "min ({min_val}) should be no larger than max ({max_val})".format(min_val=_param["min"], max_val=_param["max"])
            return _param
        
        def checkUniformParam(cls, param):
            """ """
            _param = {"min":0, "max":-1}
            _param = paramCheck(param, _param, cls.uniformParam)
            
            # check min max
            assert _param["max"] >= _param["min"], "min ({min_val}) should be no larger than max ({max_val})".format(min_val=_param["min"], max_val=_param["max"])
            return _param

        def checkPoissonParam(cls, param):
            """ """
            _param = {"mean":10, "min":0, "max":-1, "isBounded":False}
            _param = paramCheck(param, _param, cls.poissonParam)
            
            # check min max
            if _param["isBounded"]:
                assert _param["max"] >= _param["min"], "min ({min_val}) should be no larger than max ({max_val})".format(min_val=_param["min"], max_val=_param["max"])
            return _param
        
        processFuncDict = {
            "gaussian":checkGaussianParam,
            "poisson":checkPoissonParam, 
            "uniform":checkUniformParam}

        if mode:
            return processFuncDict[mode](cls, param)
        return None

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

    def __init__(self, processRate=1, mode=None, param=None, bufferSize=0, pktDropProb=0, verbose=False):
        self.mode = self.parseMode(mode)
        self.param = self.parseParam(self.mode, param)
        self.pktDropProb = pktDropProb
        
        self.bufferSize = self.parseQueueSize(bufferSize)
        self.processRate = self.parseProcessRate(processRate)

        self.verbose = verbose

        # initialize buffer
        self._initBuffer()


    """
    buffer related function
    """
    def _initBuffer(self):
        """
        initialize the buffer
        """
        self.channelBuffer = ChannelBuffer(self.bufferSize)

    def getLog(self):
        return self.channelBuffer.getLog()
    
    """
    channel operations
    """
    def putPackets(self, packetList):
        NACKPacketList = []
        pktsDropped_loss = 0
        pktDrop_fullQueue = 0
        dropPidList_loss = []
        dropPidList_fullQueue = []

        for packet in packetList:
            if self.ifKeepThePkt():
                flag = self.channelBuffer.enqueue(packet)
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
            flag, _packet = self.channelBuffer.dequeue()
            if not flag:
                break
            packetList.append(_packet)

        return packetList

    
    """
    buffer profile
    """
    def profile(self):
        """briefing each user's packet in queue"""
        return self.channelBuffer.getProfile()
    
    def printProfile(self):
        print(self.channelBuffer)



if __name__ == "__main__":
    gaussian_channel = SingleModeChannel(mode='Gaussian', param={"min":10, "max":200, "isBounded":True, "mean":120, "var":10})

    uniform_channel = SingleModeChannel(mode='uniform', param={"min":10, "max":200})

    poisson_channel = SingleModeChannel(mode='poisson', param={"mean":15})

