"""
This implementation targets at some messy confusing design.
"""

from protocols.baseTransportLayerProtocol import BaseTransportLayerProtocol
from packet import Packet, PacketInfo
from protocols.utils import Window

import sys
import logging

# logging.debug('This is a debug message')
# logging.info('This is an info message')
# logging.warning('This is a warning message')
# logging.error('This is an error message')
# logging.critical('This is a critical message')

# logging.exception("Exception occurred") # when recording exception info



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

        if verbose:
            logLevel = logging.DEBUG
        else:
            logLevel = logging.WARNING

        logging.basicConfig(
            format="%(asctime)s %(name)s:%(levelname)s:%(message)s", 
            level=logLevel,
            handlers=[
                logging.FileHandler("host-"+str(self.suid)+".log"),
                logging.StreamHandler()
            ])

        self.timeout = -1
        self.maxTxAttempts = -1
        self.maxPktTxDDL = -1

        self.verbose = verbose

        self.time = -1

        self.maxPidSent = -1

        self.parseParamByMode(params=params, requiredKeys=Window_ARQ.requiredKeys, optionalKeys=Window_ARQ.optionalKeys)

        # initialize the congestion window 
        self.window = Window(uid=suid, cwnd=self.cwnd, maxPktTxDDL=self.maxPidSent, maxTxAttempts=self.maxTxAttempts, logLevel=logLevel)


    def ticking(self, ACKPktList):
        self.time += 1

        logging.info("host-{uid}@{time}: before processing, {windowSize} pkts in cwnd".format(uid=self.suid, time=self.time, windowSize=self.window.bufferSize()))

        # process ACK packets
        self._handleACK(ACKPktList)

        # handle timeout packets
        pktsToRetransmit = self.window.getRetransPkts(curTime=self.time, RTO=self.timeout)

        # fetch new packets based on cwnd and packets in buffer
        newPktList = self._getPktsToSend()

        # print the progress if verbose=True
        if self.verbose:
            self._printProgress(
                retransPkts=pktsToRetransmit,
                newPktList=newPktList
                )

        return pktsToRetransmit + newPktList


    def _handleACK(self, ACKPktList):
        ACKPidList = []
        for pkt in ACKPktList:
            if pkt.duid == self.suid and pkt.packetType == Packet.ACK:
                ACKPidList.append(pkt.pid)
                rtt = self.time-pkt.txTime
                self._rttUpdate(rtt)
                self._timeoutUpdate()

        if self.ACKMode == "SACK":
            self.window.ACKPkts_SACK(SACKPidList=ACKPidList)
        elif self.ACKMode == "LC":
            self.window.ACKPkts_LC(LCPidList=ACKPidList)
    

    def _getPktsToSend(self):
        
        newPktNum = min(self.window.availSpace(), len(self.txBuffer))

        newPktList = []
        
        for _ in range(newPktNum):
            newpkt = self.txBuffer.popleft()
            self.distincPktsSent += 1
            self.maxPidSent = max(self.maxPidSent, newpkt.pid)

            newPktList.append(newpkt)
            
        
        self.window.pushPkts(self.time, newPktList)

        return newPktList
