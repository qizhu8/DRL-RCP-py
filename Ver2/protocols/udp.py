from protocols.baseTransportLayerProtocol import BaseTransportLayerProtocol

from collections import deque

class UDP(BaseTransportLayerProtocol):
    """
    docstring
    """
    def __init__(self, suid, duid, params={}, txBufferLen=None, verbose=False):
        super(UDP, self).__init__(suid=suid, duid=duid, params={}, txBufferLen=txBufferLen, verbose=verbose)
        
        self.protocolName="UDP"

        #for UDP, we change self.txBuffer from deque to list
        self.txBufferLen = txBufferLen
        self.time = -1
        
        self.verbose=verbose

        # performance
        self.perfDict["newPktsSent"] = 0

    def ticking(self, ACKPktList=[]):
        """
        Decide the number of packets to transmit (return) based on protocol implementation.
        """
        self.time += 1

        pktList = []

        self.perfDict["newPktsSent"] += len(self.txBuffer)
        
        while self.txBuffer:
            pkt = self.txBuffer.popleft()
            pkt.txTime = self.time
            
            self.distincPktsSent = max(self.distincPktsSent, pkt.pid)

            pktList.append(pkt)
        
        if self.verbose:
            self._printProgress(
                retransPkts=[],
                newPktList=pktList
                )
        
        return pktList
    
    def clientSidePerf(self):
        for key in self.perfDict:
            print("{key}:{val}".format(key=key, val=self.perfDict[key]))

        return self.perfDict