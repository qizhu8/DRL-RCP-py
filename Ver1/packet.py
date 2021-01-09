"""
Packet class defines the packet instance in the simulation
"""

class Packet(object):
    
    """
    Packet Type
    """
    MSG = 0
    ACK = 1
    
    def __init__(self, rttHat=0, pktLossHat=0, pid=0, suid=0, duid=0, txTime=0, initTxTime=0, txAttempts=1, packetType=MSG):
        self.pid = pid
        self.suid= suid
        self.duid= duid
        self.packetType = packetType
        self.txTime=txTime
        self.initTxTime=initTxTime
        self.txAttempts=txAttempts
        self.rttHat=rttHat
        self.pktLossHat=pktLossHat
    

    def __str__(self):
        return "{suid} -> {duid} - pid: {pid} - txTime: {txTime} - initTxTime: {initTxTime}- type: {type}".format(
            suid=self.suid, duid=self.duid, pid=self.pid, type="M" if self.packetType==0 else "A", txTime=self.txTime, initTxTime=self.initTxTime)
     

class PacketInfo(object):
    """
    A class helps to record packet info
    """
    def __init__(self, pid, suid, duid, txTime=0, initTxTime=0, txAttempts=0, rttHat=0, pktLossHat=0):
        self.pid=pid
        self.suid=suid
        self.duid=duid
        self.txTime=txTime
        self.initTxTime=initTxTime
        self.txAttempts=txAttempts
        self.rttHat=rttHat
        self.pktLossHat=pktLossHat