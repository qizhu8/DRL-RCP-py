import abc
from collections import deque

class BaseTransportLayerProtocol(object):
    """
    Base class for all protocols
    """

    requiredKeys={}
    optionalKeys={"maxTxAttempts":-1, "timeout":-1, "maxPktTxDDL":-1}

    def parseParamByMode(self, params, requiredKeys, optionalKeys):
        # required keys
        for key in requiredKeys:
            assert key in params, key +" is required for " + self.protocolName
            setattr(self, key, params[key])
        
        # optinal keys
        for key in optionalKeys:
            if key in params:
                setattr(self, key, params[key])
            else:
                setattr(self, key, optionalKeys[key])


    def __init__(self, suid, duid, params={}, txBufferLen=None, verbose=False):
        
        self.protocolName="Basic Protocl"
        self.suid=suid
        self.duid=duid
        self.verbose = verbose

        self.maxTxAttempts = -1
        self.maxPktTxDDL = -1
        self.timeout = -1
        self.parseParamByMode(params=params, requiredKeys=BaseTransportLayerProtocol.requiredKeys, optionalKeys=BaseTransportLayerProtocol.optionalKeys)

        self.txBufferLen = txBufferLen
        self.txBuffer = deque(maxlen=txBufferLen) # default to be infinite queue

        self.pktInfo_dict={} # non-acked packet info dict

        self.distincPktsSent = 0 # used as a feedback information for the server to compute delivery rate

        self.time = 0

    def _isTxBufferFull(self):
        if not self.txBuffer.maxlen:
            return False
        return len(self.txBuffer) == self.txBuffer.maxlen

    def _isExceedMaxTxAttempts(self, pid):
        if self.maxTxAttempts == -1:
            return False
        if pid in self.pktInfo_dict[pid] and self.pktInfo_dict[pid].txAttempts < self.maxTxAttempts:
            return False
        return True
    
    def _isExceedMaxRetentionTime(self, pid):
        if self.maxPktTxDDL == -1:
            return False
        if pid in self.pktInfo_dict and self.time - self.pktInfo_dict[pid].genTime < self.maxPktTxDDL:
            return False
        return True
    
    def _isPktFlying(self, pid):
        """check whether the packet is considered as transmitting and its ACK/NACK/Timeout has not been received"""
        if pid not in self.pktInfo_dict:
            return False
        else:
            return self.pktInfo_dict[pid].isFlying

    def _isPktTimeout(self, pid):
        """A packet is considered to be timeout if not ACK/NACK after timeout"""
        if pid not in self.pktInfo_dict:
            return False
        else:
            if self.time-self.pktInfo_dict[pid].txTime:
                return True
            else:
                return False


    def receive(self, pktList):
        """
        Accept packets from application layer.
        """
        numPktsToAccept = len(pktList)
        if self.txBuffer.maxlen != None:
            numPktsToAccept = min(numPktsToAccept, self.txBuffer.maxlen - len(self.txBuffer))
        
        for idx in range(len(pktList)):
            self.txBuffer.append(pktList[idx])
    
    @abc.abstractclassmethod
    def ticking(self, ACKPktList=[]):
        """
        Decide the number of packets to transmit (return) based on protocol implementation.
        """
        print("you need to implement this")
        return
        
    def _printProgress(self, retransPkts=[], newPktList=[]):
        if not retransPkts and not newPktList:
            # nothing to show
            return 
        
        if retransPkts:
            print("Client {suid}->{duid} @ {time} retransmits".format(suid=self.suid, duid=self.duid, time=self.time), end="")
            for pkt in retransPkts:
                print(" {pid}".format(pid=pkt.pid), end="")
            print()
        
        if newPktList:
            print("Client {suid}->{duid} @ {time} transmits".format(suid=self.suid, duid=self.duid, time=self.time), end="")
            for pkt in newPktList:
                print(" {pid}".format(pid=pkt.pid), end="")
            print()
        
        print("Client {suid}->{duid} @ {time}: {bufferLen} wait ACK, {txBuffer} in buffer".format(suid=self.suid, duid=self.duid, time=self.time, bufferLen=len(self.pktInfo_dict), txBuffer=len(self.txBuffer)))

        print("\t tracking ", end="")
        for pid in self.pktInfo_dict:
            print(" {}".format(pid), end="")
        print()

        return
    

