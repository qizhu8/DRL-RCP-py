from protocols.udp import UDP
# from protocols.window_arq import Window_ARQ
from protocols.window_arq_v2 import Window_ARQ
# from protocols.mcp import MCP
from protocols.mcp_v2 import MCP
from protocols.tcp_window import TCP_NewReno

class TransportLayerHelper(object):
    """
    TransportLayerHelper in charges of binding to a specific protocol implementation. 

    """
    def __init__(self, suid, duid, protocolName, params, txBufferLen=None, verbose=False):
        supportProtocols={
            "udp": UDP,
            "window arq":Window_ARQ,
            "mcp": MCP,
            "tcp_newreno": TCP_NewReno,
        }
        self.suid = suid
        self.duid = duid
        
        self.protocolName = protocolName.lower()
        assert self.protocolName in supportProtocols, protocolName + " is not supported. Choose from "+list(supportProtocols.keys).__str__()
        self.instance = supportProtocols[self.protocolName](suid=suid, duid=duid, params=params, txBufferLen=txBufferLen, verbose=verbose)
        self.protocolName = self.instance.protocolName # some protocol will add a more detailed suffix, e.g. ARQ_finit_window


    def receiveFromApplication(self, pktList):
        self.instance.receive(pktList)
    
    def sendPkts(self, ACKPktList=[]):
        return self.instance.ticking(ACKPktList=ACKPktList)
    
    def getDistinctPktSent(self):
        return self.instance.distincPktsSent
