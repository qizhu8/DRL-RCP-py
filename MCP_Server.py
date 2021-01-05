"""
This server sends back not only ACK but also NACK. This is not realistic in real applications, but is helpful when purely evaluating the MCP_Client.
"""

from Applications import SimpleServer
from packet import Packet

class MCP_Server(SimpleServer):
    """
    docstring
    """
    def __init__(self, serverId, verbose=False):

        SimpleServer.__init__(self, serverId=serverId, isACK=True, ACKMode="SACK", verbose=verbose)

        # performance counter
        self.pktInfo = {}
        self.maxSeenPid = -1
    
    def ACK(self, packet):
        """ACK a packet"""
        if packet.duid != self.serverId:
            """wrong destination"""
            return []

        self.pktInfo[packet.pid] = self.time - packet.initTxTime
        self.maxSeenPid = max(self.maxSeenPid, packet.pid)

        packet.duid=packet.suid
        packet.suid=self.serverId
        packet.packetType=Packet.ACK
        

        return [packet]
        
    

    def serverSidePerf(self, clientPid=-1):
        if clientPid > 0:
            # we know that the client tries to send clientPid packets
            self.maxSeenPid = clientPid
        
        # overall delivery prob 
        sumDelay = 0
        deliveriedPkts = len(self.pktInfo)

        for key in self.pktInfo:
            sumDelay += self.pktInfo[key]
        avgDelay = sumDelay / deliveriedPkts

        return deliveriedPkts, deliveriedPkts/self.maxSeenPid, avgDelay

    def printPerf(self, clientPid=-1):
        deliveriedPkts, deliveryRate, avgDelay = self.serverSidePerf(clientPid)
        print("Server {} Performance:".format(self.serverId))
        print("%d pkts delivered" % deliveriedPkts)
        print("{} percent delivery rate".format(deliveryRate))
        print("average delay {}".format(avgDelay))