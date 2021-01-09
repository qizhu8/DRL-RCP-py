from protocols.baseTransportLayerProtocol import BaseTransportLayerProtocol

class TCP_Reno(BaseTransportLayerProtocol):
    
    def __init__(self, suid, duid, params, txBufferLen=-1):
        BaseTransportLayerProtocol.__init__(self, suid=suid, duid=duid, params=params, txBufferLen=txBufferLen)
    
        self.time = -1
    
    def ticking(self, ACKPktList=[]):
        self.time += 1