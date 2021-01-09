"""
The original design in Ver1 is chaoatic. In this design, application.py only incharge of the Application layer of the 4-layer network stack (not the OSI, but the TCP/IP stack). 
"""
import numpy as np

from packet import Packet
from transportLayer import TransportLayerHelper


class EchoClient(object):
    """
    EchoClient in charges of generating packets to sent to the server.
    Support traffic patterns:
    {"periodic", "random"}

    Common attributes:
        id: int, id of the the client. used to simulate the IP address
        serverId: int, whom to talk to
        transportObj: a transport layer instance (e.g. TCP, UDP instance)

    1. periodic: {"period": period, "pktPerPeriod":pktPerPeriod, "startTime":startTime, "lastTime":lastTime}
        $pktPerPeriod packets are periodically generated at the begining of each period. 
        param:
            period:         int
            pktPerPeriod:   int
            startTime:       int, optional, default 0, when to start generating the traffic
            lastTime:       int, optional, default -1, generate the traffic for how long, -1 if forever
    2. poisson: {"lambda":lambda, "startTime":startTime, "lastTime":lastTime}
        Generate traffic following poisson distribution
        param:
            lambda:         int, lambda of the poisson distribution
            startTime:       int, optional, default 0, when to start generating the traffic
            lastTime:       int, optional, default -1, generate the traffic for how long, -1 if forever
    """

    def parseTrafficSettings(self, trafficMode, trafficParam):
        def parseParamByMode(trafficMode, requiredKeys, optionalKeys):
            self.trafficMode = trafficMode

            # required keys
            for key in requiredKeys:
                assert key in trafficParam, key +" is required for " + self.trafficMode
                # setattr(self, key, trafficParam[key])
                self.trafficParam[key] = trafficParam[key]
            
            # optinal keys
            for key in optionalKeys:
                if key in trafficParam:
                    # setattr(self, key, trafficParam[key])
                    self.trafficParam[key] = trafficParam[key]
                else:
                    # setattr(self, key, optionalKeys[key])
                    self.trafficParam[key] = optionalKeys[key]

        def parsePeriodicParam(trafficParam):
            requiredKeys = {"period", "pktsPerPeriod"}
            optionalKeys = {"startTime":0, "lastTime":-1}
            parseParamByMode(trafficMode="periodic", requiredKeys=requiredKeys, optionalKeys=optionalKeys)
        
        def parsePoissonParam(trafficParam):
            requiredKeys = {"lambda"}
            optionalKeys = {"startTime":0, "lastTime":-1}
            parseParamByMode(trafficMode="poisson", requiredKeys=requiredKeys, optionalKeys=optionalKeys)
        
        trafficParamHandleDict = {
            "periodic": parsePeriodicParam,
            "poisson": parsePoissonParam
        }
        assert isinstance(trafficMode, str), "trafficMode must be string"
        trafficMode = trafficMode.lower()
        assert trafficMode in trafficParamHandleDict, "support traffic modes are " + list(trafficParamHandleDict.keys).__str__()

        trafficParamHandleDict[trafficMode](trafficParam)
        

    def __init__(self, clientId, serverId, protocolName, transportParam, trafficMode, trafficParam, txBufferLen=None, verbose=False):
        self.uid = clientId
        self.duid = serverId
        self.verbose = verbose

        self.startTime=-1
        self.lastTime=-1
        self.trafficMode=""
        self.trafficParam={}
        self.parseTrafficSettings(trafficMode=trafficMode, trafficParam=trafficParam)

        self.transportObj = TransportLayerHelper(suid=self.uid, duid=self.duid, protocolName=protocolName, params=transportParam, txBufferLen=txBufferLen, verbose=verbose)

        # init time
        self.time = -1
        
        # packet id
        self.pid = 0 
        # binding traffic generator
    
    def ticking(self, ACKPktList=[]):
        self.time += 1
        # generate packets
        pktList = self.trafficGenerator()
        # feed packets to transport layer
        self.transportObj.receiveFromApplication(pktList)

        pktToSend = self.transportObj.sendPkts(ACKPktList)
        
        return pktToSend

    def trafficGenerator(self):
        def periodicTrafficGenerator():
            if (self.time - self.trafficParam["startTime"]) % self.trafficParam["period"] == 0:
                return self._genNewPkts(self.trafficParam["pktsPerPeriod"])
            else:
                return []
        
        def poissonTrafficGenerator():
            pktNum = np.random.poisson(lam=self.trafficParam["lambda"])
            return self._genNewPkts(pktNum)

        # check start and end time
        if self.time <= self.trafficParam["startTime"]:
            return []
        if self.trafficParam["lastTime"] != -1 and \
            self.time > self.trafficParam["lastTime"]+self.trafficParam["startTime"]:
            return []
        
        pktGenHandleDict = {
            "periodic": periodicTrafficGenerator,
            "poisson": poissonTrafficGenerator
        }

        return pktGenHandleDict[self.trafficMode]()

    def _genNewPkts(self, pktNum):
        """Generate $packetNumber new packets"""
        num = 0
        pktList = []
        while num < pktNum:
            pktList.append(
                Packet(
                    pid=self.pid,
                    suid=self.uid,
                    duid=self.duid,
                    genTime=self.time,
                    packetType=Packet.MSG
                )
            )
            self.pid += 1
            num += 1
        return pktList
    
    def getDistinctPktSent(self):
        return self.transportObj.getDistinctPktSent()
    
            
            
class EchoServer(object):
    """
    docstring
    """
    def parseACKMode(self, ACKMode):
        if ACKMode == None:
            return ACKMode
        assert isinstance(ACKMode, str), "ACKMode should be None or a string" 
        ACKMode = ACKMode.upper()
        assert ACKMode in {"LC", "SACK"}, "ACKMode should be None or LC or SACK" 
        return ACKMode

    def __init__(self, serverId, ACKMode=None, verbose=False):
        self.uid=serverId
        self.verbose = verbose

        # packet ack counter, the latest sequential ack
        self.ACKMode = self.parseACKMode(ACKMode)
        self.ack = -1 # last ACKed packet id or maximum packet id 

        # time
        self.time = -1

        # performance counter
        self.pktInfo = {}
        self.maxSeenPid = -1

    def ticking(self, pktList):
        self.time += 1

        ACKPktList = self._handlePkts(pktList)

        return ACKPktList


    def _handlePkts(self, pktList=[]):
        usefulPktList = []
        for pkt in pktList:
            if pkt.duid != self.uid:
                continue
            usefulPktList.append(pkt)
        
        if not self.ACKMode:
            return self._handlePktList_None(usefulPktList)
        if self.ACKMode == "SACK":
            return self._handlePktList_SACK(usefulPktList)
        if self.ACKMode == "LC":
            return self._handlePktList_LC(usefulPktList)

    def _handlePktList_None(self, usefulPktList):
        for pkt in usefulPktList:
            self.pktInfo[pkt.pid] = self.time - pkt.genTime
            self.maxSeenPid = max(self.maxSeenPid, pkt.pid)
        return []


    def _handlePktList_SACK(self, usefulPktList):
        ACKPacketList = []
        

        for pkt in usefulPktList:
            self.pktInfo[pkt.pid] = self.time - pkt.genTime
            self.maxSeenPid = max(self.maxSeenPid, pkt.pid)

            pkt.duid, pkt.suid = pkt.suid, pkt.duid
            pkt.packetType = Packet.ACK
            ACKPacketList.append(pkt)
        return ACKPacketList

    def _handlePktList_LC(self, usefulPktList):
        ACKPacketList = []
        usefulPktList.sort(key=lambda r:r.pid)

        ACKNewPktList = []
        for pkt in usefulPktList:
            if pkt.pid == (self.ack+1):
                self.ack=pkt.pid
                if self.verbose:
                    ACKNewPktList.append(pkt.pid)
            self.pktInfo[pkt.pid] = self.time - pkt.genTime
            self.maxSeenPid = max(self.maxSeenPid, pkt.pid)
            
            pkt.duid, pkt.suid = pkt.suid, pkt.duid
            pkt.packetType = Packet.ACK
            pkt.pid = self.ack
            ACKPacketList.append(pkt)

        if self.verbose and ACKNewPktList:
            print("Server {} ACKs @ {}: ".format(self.uid, self.time), end="")
            for pid in ACKNewPktList:
                print(" {}".format(pid), end="")
            print()
        
        return ACKPacketList

    def serverSidePerf(self, clientPid=-1):
        
        if clientPid >= 0:
            # we know that the client tries to send clientPid packets
            self.maxSeenPid = clientPid

        # overall delivery prob 
        sumDelay = 0
        if self.ACKMode == "LC":
            deliveriedPkts = self.ack+1
            for pid in range(self.ack+1):
                sumDelay += self.pktInfo[pid]
        else:
            deliveriedPkts = len(self.pktInfo)
            for pid in self.pktInfo:
                sumDelay += self.pktInfo[pid]
        
        # deal with divide by 0 problem
        if deliveriedPkts != 0:
            avgDelay = sumDelay / deliveriedPkts
        else:
            avgDelay = -1
        
        deliveryRate = deliveriedPkts/(self.maxSeenPid+1) # +1 because pid starts from 0

        return deliveriedPkts, deliveryRate, avgDelay

    def printPerf(self, clientPid=-1):
        deliveriedPkts, deliveryRate, avgDelay = self.serverSidePerf(clientPid)
        print("Server {} Performance:".format(self.uid))
        print("\tpkts received  %d out of %d" % (deliveriedPkts, self.maxSeenPid+1))
        print("\tdelivery rate  {}% ".format(deliveryRate*100))
        print("\taverage delay  {}".format(avgDelay))