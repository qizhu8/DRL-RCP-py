import abc
from collections import deque

class BaseTransportLayerProtocol(object):
    """
    Base class for all protocols
    """

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

        self.parseParamByMode(params=params, requiredKeys={}, optionalKeys={})

        self.txBufferLen = txBufferLen
        self.txBuffer = deque(maxlen=txBufferLen) # default to be infinite queue

        self.pktInfo_dict={} # non-acked packet info dict

        self.distincPktsSent = 0 # used as a feedback information for the server to compute delivery rate

        self.time = 0

    def _isTxBufferFull(self):
        if not self.txBuffer.maxlen:
            return False
        return len(self.txBuffer) == self.txBuffer.maxlen


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
        
        print("Client {suid}->{duid} @ {time} {bufferLen} wait ACK {txBuffer} in buffer".format(suid=self.suid, duid=self.duid, time=self.time, bufferLen=len(self.pktInfo_dict), txBuffer=len(self.txBuffer)))
    
        return
    

