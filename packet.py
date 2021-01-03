"""
Packet class defines the packet instance in the simulation
"""

class Packet(object):
    
    """
    Packet Type
    """
    MSG = 0
    ACK = 1
    
    def __init__(self, pid=0, suid=0, duid=0, packetType=MSG):
        self.pid = pid
        self.suid= suid
        self.duid= duid
        self.packetType = packetType
    

    def __str__(self):
        return "{suid} -> {duid} - pid: {pid} - type: {type}".format(suid=self.suid, duid=self.duid, pid=self.pid, type="M" if self.packetType==0 else "A")
     