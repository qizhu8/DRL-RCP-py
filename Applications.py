from packet import Packet
import random

class SimpleServer(object):
    """
    server only incharge of accept packets from the channel.
    no rwind implementation, i.e. rwind=infinity
    We implement two types of server:
    1. with ACK
        1.1 SACK mode: ACK any packet without check packet id
        1.2 LC mode: ACK only the consequent packet
    2. without ACK
    """
    
    def __init__(self, serverId, isACK=False, ACKMode=None, verbose=False):
        """
        Parameters:
            serverId: int
            isACK: bool whether to send ACK once accept a packet
            ACKMode: str "LC"/"SACK"/None
                LC: Largest consequent packet id
                SACK: packet id 
                None: no ACK
        """
        self.serverId = serverId
        self.isACK = isACK
        self.verbose = verbose

        # packet ack counter, the latest sequential ack
        self.ACKMode = ACKMode
        self.ack = -1

    def ticking(self, packetList):
        """server checks packets """
        ACKPacketList = []


        if packetList:
            if self.verbose:
                print("Server {} acks pkts".format(self.serverId), end="")
            for packet in packetList:
                flag, ACKPacket = self.ACK(packet)
                if flag:
                    ACKPacketList.append(ACKPacket)
                    if self.verbose:
                        print(" {}".format(ACKPacket.pid), end="")
            if self.verbose:
                print()
        return len(ACKPacketList) > 0,  ACKPacketList

    def ACK(self, packet):
        """ACK a packet"""
        if packet.duid != self.serverId:
            """wrong destination"""
            return False, []

        if self.ACKMode == "SACK":
            return True, Packet(pid=packet.pid, suid=self.serverId, duid=packet.suid, packetType=Packet.ACK)
        if self.ACKMode == "LC":
            if packet.pid == self.ack+1:
                self.ack = packet.pid
            return True, Packet(pid=self.ack, suid=self.serverId, duid=packet.suid, packetType=Packet.ACK)
        
        return False, []


class SimpleClient(object):
    """
    A simple client. 

    1. periodic send packets 
        send $pktsPerPeriod packets at the begining of each period
    2. burst packet transmission
        send $pktsPerPeriod/$duration packets at the begining $duration ticks of each period 

    No ARQ, simply generates some random traffic to fill the channel
    """
    supportModes = {"periodic", "window arq"}


    @classmethod
    def parseAppMode(cls, appMode):
        assert isinstance(appMode, str), "appMode should be a string"
        appMode = appMode.lower()
        assert appMode in cls.supportModes, \
            "appMode " + appMode + " is not supported. Please choose from " + cls.supportModes
        return appMode

    def parseParam(self, param):
        
        def parseParamByMode(trafficMode, requiredKeys, optionalKeys):
            self.trafficMode = trafficMode

            # required keys
            for key in requiredKeys:
                assert key in param, key +" is required for " + self.trafficMode
                setattr(self, key, param[key])
            
            # optinal keys
            optionalKeys = {"ACKMode":None}
            for key in optionalKeys:
                if key in param:
                    setattr(self, key, param[key])
                else:
                    setattr(self, key, optionalKeys[key])


        def parsePeriodicParam(self, param):
            """
            parse param for periodic mode.
            """
            requiredKeys = {"period", "pktsPerPeriod", "offset"}
            optionalKeys = {"ACKMode":None}
            parseParamByMode(trafficMode="periodic", requiredKeys=requiredKeys, optionalKeys=optionalKeys)

        
        def parseWindowARQParam(self, param):
            """
            parse param for window ARQ mode.
            """
            requiredKeys = {"cwnd", "ACKMode"}
            optionalKeys = {}
            parseParamByMode(trafficMode="window arq", requiredKeys=requiredKeys, optionalKeys=optionalKeys)

        
        parseParamDict = {
            "periodic": parsePeriodicParam,
            "window arq": parseWindowARQParam
        }
        parseParamDict[self.appMode](self, param)

    def __init__(self, clientId, serverId, timeout=3, appMode="periodic", param={"period":3, "pktsPerPeriod": 1, "offset": 5, "ACKMode": None}, verbose=False):
        # default attributes
        self.period = 0
        self.trafficMode = ""
        self.pktsPerPeriod = 0
        self.trafficOffset = 0
        self.ACKMode = None

        self.clientId = clientId
        self.serverId = serverId
        self.appMode = SimpleClient.parseAppMode(appMode)
        self.parseParam(param)

        self.timeout = timeout
        self.lastACK_LC = -1
        self.lastACKCounter_LC = 0
        self.pktsNACKed_SACK = dict()

        self.verbose = verbose

        # initialize scheduler
        self.time = 0 # current time
        # we use state machine to generate traffic
        self.state = 0
        self.pid = 0
    
    def setTimeout(self, timeout):
        self.timeout = time

    def _transmitNewPacket(self):

        def _transmitNewPacket_periodic(self):
            # generate new packets based on the current state
            self.state = (self.state + 1) % self.period

            newPacketList = []
            if self.time > self.trafficOffset:
                if self.state == 0: # send packets at the begining of the period
                    if self.verbose:
                        print("Client {} transmits ".format(self.clientId), end="")
                    for _ in range(self.pktsPerPeriod):
                        newPacketList.append(Packet(
                            pid=self.pid, 
                            suid=self.clientId,
                            duid=self.serverId,
                            packetType=Packet.MSG))
                        if self.verbose:
                            print(" {}".format(self.pid), end="")
                        
                        if self.ACKMode == "SACK":
                            self.pktsNACKed_SACK[self.pid] = 0
                        self.pid += 1
                    if self.verbose:
                        print()
            
            return newPacketList

        def _transmitNewPacket_ARQ(self):
            # determine the number of new packets based on packets waiting for ACKs
            newPacketList = []
            if self.ACKMode == "SACK":
                numOfNewPackets = self.cwnd - len(self.pktsNACKed_SACK)
            elif self.ACKMode == "LC":
                numOfNewPackets = self.cwnd - (self.pid - self.lastACKCounter_LC)
            else:
                raise "ARQ mode not support"

            if numOfNewPackets > 0:
                if self.verbose:
                        print("Client {} transmits ".format(self.clientId), end="")
                for _ in range(numOfNewPackets):
                    newPacketList.append(Packet(
                            pid=self.pid, 
                            suid=self.clientId,
                            duid=self.serverId,
                            packetType=Packet.MSG))
                    if self.verbose:
                        print(" {}".format(self.pid), end="")
                    
                    if self.ACKMode == "SACK":
                        self.pktsNACKed_SACK[self.pid] = 0
                    self.pid += 1
                if self.verbose:
                    print()
            
            return newPacketList 

        genNewPakcetListDict = {
            "periodic": _transmitNewPacket_periodic,
            "window arq": _transmitNewPacket_ARQ
        }

        return genNewPakcetListDict[self.appMode](self)

    def _handleACK(self, ACKPacketList):
        
        def _handleACK_LC():
            packetList = []
            lastACK_LC_old = self.lastACK_LC
            for packet in ACKPacketList:
                if packet.duid == self.clientId:
                    self.lastACK_LC = max(self.lastACK_LC, packet.pid)

            
            if self.lastACK_LC < (self.pid-1) and self.lastACK_LC == lastACK_LC_old:
                self.lastACKCounter_LC += 1
            else:
                self.lastACKCounter_LC = 0

            # print("lastACK_LC=%d self.lastACKCounter_LC=%d pid=%d " % (self.lastACK_LC, self.lastACKCounter_LC, self.pid))

            if self.lastACKCounter_LC >= self.timeout:
                for pid in range(self.lastACK_LC+1, self.pid+1):
                    packetList.append(Packet(
                        pid=pid, 
                        suid=self.clientId,
                        duid=self.serverId,
                        packetType=Packet.MSG))
            
            return packetList

        def _handleACK_SACK():
            # remove pkts from buffer for those whom ACKs are received
            packetList = []
            for packet in ACKPacketList:
                if packet.duid == self.clientId:
                    self.pktsNACKed_SACK.pop(packet.pid, None)

            # check whether there is a packet needs retransmission
            # retransmit NACKed packets
            
            for pid in self.pktsNACKed_SACK:
                self.pktsNACKed_SACK[pid] += 1
                if self.pktsNACKed_SACK[pid] >= self.timeout:
                    self.pktsNACKed_SACK[pid] = 0
                    packetList.append(Packet(
                        pid=pid, 
                        suid=self.clientId,
                        duid=self.serverId,
                        packetType=Packet.MSG))
                    
            return packetList
        
        def _handleACK_None():
            return []

        handleACKFuncDict = {
            "LC": _handleACK_LC,
            "SACK": _handleACK_SACK
        }


        return handleACKFuncDict[self.ACKMode]()

    def ticking(self, ACKPacketList=[]):
        """
        client actions in each time slot (tick)
        1. check ACK and decides which packet to retransmit
        2. transmit new packets
        """
        self.time += 1
        packetList = []

        # process ACK
        if self.ACKMode:
            packetList += self._handleACK(ACKPacketList)
                        
            if self.verbose and packetList:
                print("Client {} retransmits ".format(self.clientId), end="")
                for packet in packetList:
                    print(" {}".format(packet.pid), end="")
                print()

        # generate new packets
        # flag, newPacketList = self._transmitNewPacket()
        packetList += self._transmitNewPacket()

        return len(packetList) > 0, packetList 


if __name__ == "__main__":

    """
    periodic examples
    """

    # client1 = SimpleClient(clientId=1, serverId=2, appMode="periodic", param={"period":3, "pktsPerPeriod": 4, "offset": 5, "ACKMode": "SACK"}, verbose=True)

    """
    window arq example
    """
    client1 = SimpleClient(clientId=1, serverId=2, appMode="window arq", param={"cwnd":3, "offset": 5, "ACKMode": "SACK"}, verbose=True)

    server1 = SimpleServer(serverId=2, ACKMode="SACK", verbose=True)

    ACKPacketList = []
    tmpPacketList = []

    for time in range(70):

        print("=="*10)
        print("time ", time)

        flag, packetList = client1.ticking(ACKPacketList=ACKPacketList)


        # manually drop some packets
        if time > 40 and time < 60:
            """mode 1: drop all packets
            if packetList:
                if len(packetList) > 1:
                    print("[-] manually drop packet ", end="")
                for packet in packetList:
                    print(" {pid}".format(pid=packet.pid), end="")
                print()
                packetList = []
            #"""
            """
            # mode 2: slow channel
            tmpPacketList += packetList
            if tmpPacketList:
                packetList = [tmpPacketList[0]]
                tmpPacketList = tmpPacketList[1:]
            else:
                packetList = []
            
        else:
            packetList += tmpPacketList
            tmpPacketList = []
            #"""
            #"""
            # mode 3: random drop channel
            print("[-] manually drop packet ", end="")
            tmpPacketList = []
            for idx in range(len(packetList)):
                if random.random() > 0.5: # packet drop rate 
                    tmpPacketList.append(packetList[idx])
                else:
                    print(" {pid}".format(pid=packetList[idx].pid), end="")
            print()
            packetList.clear()
            packetList += tmpPacketList
            tmpPacketList.clear()
            #"""

        flag, ACKPacketList = server1.ticking(packetList)