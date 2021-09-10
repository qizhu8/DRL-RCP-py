from protocols.baseTransportLayerProtocol import BaseTransportLayerProtocol
from packet import Packet, PacketInfo


class Window_ARQ(BaseTransportLayerProtocol):
    """
    General working procedure:

    In each time slot, sends at most cwnd packets from the top of the txBuffer. Each packet remains in pktInfo dictionary unless
    1. ACKed
    2. exceeds maximum transmission attempts (maxTxAttempts) or exceeds maximum pkt retention time (maxPktTxDDL)

    A transmitted packet will trigger the retransmission process if :
    1. NACKed (sent by channel)
    2. not ACKed after timeout

    Once a packet needs retransmission, it is pushed at the top of the transmission buffer (txBuffer)
    """

    requiredKeys={"cwnd", "ACKMode"}
    optionalKeys={"maxTxAttempts":-1, "timeout":30, "maxPktTxDDL":-1}

    def __init__(self, suid, duid, params, txBufferLen=None, verbose=False):
        super(Window_ARQ, self).__init__(suid=suid, duid=duid, params={}, txBufferLen=txBufferLen)
        
        self.protocolName="Window ARQ"
        self.cwnd = 0
        self.maxTxAttempts = 0
        self.timeout = 0
        

        # ACKMode
        self.ACKMode = ""
        self.pktInfo_dict = {}
        # LC param
        self.pid_LC = -1
        
        self.verbose = verbose

        self.time = -1

        self.maxPidSent = -1

        self.parseParamByMode(params=params, requiredKeys=Window_ARQ.requiredKeys, optionalKeys=Window_ARQ.optionalKeys)


    def ticking(self, ACKPktList=[]):
        self.time += 1

        pidConsiderRetrans = []
        # process ACK and NACK packets
        pidConsiderRetrans += self._handleACK(ACKPktList)

        # handle timeout packets
        pidConsiderRetrans += self._handleTimeoutPkts()

        # push retrans packets in buffer
        self._pushBackPktsToRetrans(pidConsiderRetrans)

        # generate new packets
        newPktList, retransPktList = self._getPktsToSend()

        # print the progress if verbose=True
        if self.verbose:
            self._printProgress(
                retransPkts=retransPktList,
                newPktList=newPktList
                )

        return retransPktList + newPktList
    
    def _pushBackPktsToRetrans(self, pidConsiderRetrans):
        # remove redundant

        pidConsiderRetrans = list(set(pidConsiderRetrans))
        pidConsiderRetrans.sort(reverse=True)
        
        for pid in pidConsiderRetrans:
            if self._isPktTimeout(pid) and not self._isPktFlying(pid):
                self.txBuffer.appendleft(self.pktInfo_dict[pid].toPacket())
                



    def _getPktsToSend(self):
        newPktList = []
        retransPktList = []

        numPktsFlying = 0
        for pid in self.pktInfo_dict:
            if self.pktInfo_dict[pid].isFlying:
                numPktsFlying += 1

        numOfNewPackets = min(self.cwnd-numPktsFlying, len(self.txBuffer))
        numOfNewPackets = max(numOfNewPackets, 0)

        # print("numPktsFlying:", numPktsFlying, "numOfNewPkts", numOfNewPackets)

        for _ in range(numOfNewPackets):
            pkt = self.txBuffer.popleft()
            pkt.txTime = self.time

            if pkt.pid in self.pktInfo_dict:
                self.pktInfo_dict[pkt.pid].txTime = self.time
                self.pktInfo_dict[pkt.pid].txAttempts += 1
                self.pktInfo_dict[pkt.pid].isFlying = True
                retransPktList.append(pkt)
            else:
                self.pktInfo_dict[pkt.pid] = self._genNewPktInfoFromPkt(pkt)
                if pkt.pid > self.maxPidSent:
                    self.distincPktsSent += 1
                    self.maxPidSent = pkt.pid

                newPktList.append(pkt)
        
        return newPktList, retransPktList
    
    def _genNewPktInfoFromPkt(self, pkt):
        pktInfo = PacketInfo(
            pid=pkt.pid, 
            suid=pkt.suid, 
            duid=pkt.duid,
            txTime=pkt.txTime,
            genTime=pkt.genTime,
            initTxTime=pkt.txTime, 
            txAttempts=1,
            isFlying=True
            )

        return pktInfo
    
    def _handleACK(self, ACKPktList):

        NACKList, ACKList = [], []
        for pkt in ACKPktList:
            if pkt.duid != self.suid:
                continue
            if pkt.pid not in self.pktInfo_dict:
                continue
            if pkt.packetType == Packet.ACK:
                ACKList.append(pkt)
            elif pkt.packetType == Packet.NACK:
                NACKList.append(pkt)

        pidConsiderRetrans = self._handleNACK(NACKList)
        if self.ACKMode == "SACK":
            self._handleACK_SACK(ACKList)
        elif self.ACKMode == "LC":
            self._handleACK_LC(ACKList)
        
        return pidConsiderRetrans

    def _handleACK_SACK(self, ACKPktList):
        for pkt in ACKPktList:
            if pkt.pid in self.pktInfo_dict:
                self.pktInfo_dict.pop(pkt.pid, None)
    
    def _handleACK_LC(self, ACKPktList):
        if not ACKPktList:
            return 

        maxACKedPid = -1
        for pkt in ACKPktList:
            maxACKedPid = max(maxACKedPid, pkt.pid)
        
        pidsInDict = list(self.pktInfo_dict.keys())
        for pid in pidsInDict:
            if pid <= maxACKedPid:
                self.pktInfo_dict.pop(pid, None)
    
    def _handleNACK(self, NACKPacketList):
        pidConsiderRetrans = []
        for pkt in NACKPacketList:
            if self._isPktFlying(pkt.pid):
                # we do track this packet
                self.pktInfo_dict[pkt.pid].isFlying = False
                pidConsiderRetrans.append(pkt.pid)
        return pidConsiderRetrans
    

    def _handleTimeoutPkts(self):
        pidConsiderRetrans = []
        pidsToCheck = list(self.pktInfo_dict.keys())
        pidsToCheck.sort(reverse=True)
        for pid in pidsToCheck:
            pidConsiderRetrans += self._handleTimeoutPkt(pid)
        
        return pidConsiderRetrans

    def _handleTimeoutPkt(self, pid):
        if self.timeout == -1: # disable this function
            return []

        # check whether the packet still worth to stay in buffer
        if not self._isExceedMaxTxAttempts(pid) and not self._isExceedMaxRetentionTime(pid):
            # determine a packet to be timedout 
            if self._isPktTimeout(pid):
                self.pktInfo_dict[pid].isFlying = False
                return [pid]
                
        else:
            # print("[-] ignore ", pid)
            self.pktInfo_dict.pop(pid, None) # ignore this packet
            return []

        return []