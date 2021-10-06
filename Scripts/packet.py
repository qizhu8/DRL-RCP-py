"""
Packet class defines the packet instance in the simulation
"""

class Packet(object):
    
    """
    Packet Type
    """
    MSG = 0
    ACK = 1
    NACK = 2
    
    def __init__(self, pid=0, suid=0, duid=0, genTime=0, txTime=0, packetType=MSG):
        self.pid = pid
        self.suid= suid
        self.duid= duid
        self.packetType = packetType
        self.genTime = genTime 
        self.txTime=txTime
        # self.txAttempts=txAttempts
        
        # self.initTxTime=initTxTime
        # self.rttHat=rttHat
        # self.pktLossHat=pktLossHat
    

    def __str__(self):
        return "{suid} -> {duid}  pid:{pid} tx@:{txTime} gen@:{genTime} type: {type}".format(
            suid=self.suid, duid=self.duid, 
            pid=self.pid, 
            txTime=self.txTime, genTime=self.genTime,
            type="M" if self.packetType==0 else "A" )
     
    def __lt__(self, otherPkt):
        return self.pid <= otherPkt.pid

class PacketInfo(object):
    """
    A class helps to record packet info
    """
    def __init__(self, pid, suid, duid, genTime=0, txTime=0, initTxTime=0, txAttempts=0, isFlying=True, util=0, RLState=[]):
        self.pid=pid
        self.suid=suid
        self.duid=duid
        self.genTime=genTime
        self.txTime=txTime
        self.initTxTime=initTxTime
        self.txAttempts=txAttempts
        self.isFlying=isFlying
        self.RLState=RLState
        self.util=util
    
    def toPacket(self):
        pkt = Packet(
            pid= self.pid,
            suid= self.suid,
            duid= self.duid,
            packetType = Packet.MSG, # the only application I can think about is to generate a Message Packet
            genTime = self.genTime,
            txTime=self.txTime,
        )
        return pkt

    def __str__(self):
        return "Packet Info: pid:{pid} {suid}->{duid} gen@{genTime} initTx@{initTxTime} lastTx@{txTime} txAttempts:{txAttempts} isFlying:{isFlying}".format(pid=self.pid, suid=self.suid, duid=self.duid, genTime=self.genTime, txTime=self.txTime, initTxTime=self.initTxTime, txAttempts=self.txAttempts, isFlying=self.isFlying)