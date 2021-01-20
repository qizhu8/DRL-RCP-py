from protocols.baseTransportLayerProtocol import BaseTransportLayerProtocol
from packet import Packet, PacketInfo

from collections import deque
import sys

class TCP_NewReno(BaseTransportLayerProtocol):
    
    requiredKeys={"timeout"}
    optionalKeys={"IW":4} # no maximum retransmission

    SLOW_START = 0
    RETRANSMISSION = 1
    FAST_RETRANSMISSION = 2
    CONGESTION_AVOIDANCE = 3
    FAST_RECOVERY = 4

    def __init__(self, suid, duid, params, txBufferLen=-1, verbose=False):
        super(TCP_NewReno, self).__init__(suid=suid, duid=duid, params={}, txBufferLen=txBufferLen)
    
        self.protocolName="TCP NewReno"
        self.verbose = verbose

        # for TCP reno, only packet not ACK are in pktInfo => NACK/Timeout will be wiped out and moved to txBuffer
        self.pktInfo_dict={} 

        self.IW = 4 # initial cwnd window
        self.maxTxAttempts = -1
        self.maxPktTxDDL = -1

        self.timeout = -1

        self.parseParamByMode(params=params, requiredKeys=TCP_NewReno.requiredKeys, optionalKeys=TCP_NewReno.optionalKeys)

        

        self.pktToRetransmit = []
        self.cwnd = self.IW
        self.cwnd_inc_counter = 0 # for congestion avoidance mode. +1 for one ACK. cwnd+1 when cwnd_inc_counter >= cwnd
        self.curTxMode = TCP_NewReno.SLOW_START
        self.ssthresh = sys.maxsize # slow start threshold (init value: inf)

        self.lastACKCounter = [-1, 0] # [ACK.pid, showup times]

        self.time = 0
        
        self.maxPidSent = -1
        self.high_water = -1 # 
        self.distincPktsSent = 0 # used as a feedback information for the server to compute delivery rate

    
    def ticking(self, ACKPktList=[]):
        self.time += 1 
        
        oldCwnd=self.cwnd

        self._handleACK(ACKPktList)
        # print("@{} after ACK cwnd={} ssthres={} mode={}".format(self.time, self.cwnd, self.ssthresh, self.curTxMode))

        # handle timeout packets if any
        self._handleTimeoutPkts()

        # generate new packets
        pktList = self._getPktsToSend()

        # print the progress if verbose=True
        if self.verbose:
            self._printProgress(
                retransPkts=[],
                newPktList=pktList
                )
            print("Client {suid}->{duid} @ {time} cwnd: {oldCwnd}->{cwnd}".format(
                suid=self.suid, duid=self.duid, time=self.time, oldCwnd=oldCwnd, cwnd=self.cwnd
            ))
        return pktList
    
    def _handleACK(self, ACKPktList):
        # filter out ACK and NACK
        # process ACK
        ACKPidList = []
        for pkt in ACKPktList:
            if pkt.duid != self.suid:
                continue
            if pkt.packetType == Packet.ACK:
                ACKPidList.append(pkt.pid)
                # update rtt
                if pkt.pid in self.pktInfo_dict:
                    rtt = self.time-self.pktInfo_dict[pkt.pid].txTime
                    self._rttUpdate(rtt)
            
            # TCP reno doesn't have NACK
            # elif pkt.packetType == Packet.NACK: 
            #     NACKList.append(pkt.pid)
        

        self._handleACK_reno(ACKPidList)

        return

    def _handleACK_reno(self, ACKPidList):
        """
        cwnd 
        """
        def cwndIncrement_SS():
            self.cwnd += 1
            if self.cwnd >= self.ssthresh:
                self.curTxMode = TCP_NewReno.CONGESTION_AVOIDANCE
                self.cwnd_inc_counter = 0
        
        def cwndIncrement_CA():
            self.cwnd_inc_counter += 1
            if self.cwnd_inc_counter >= self.cwnd:
                self.cwnd += 1
                self.cwnd_inc_counter -= self.cwnd

        cwndIncrementFuncDict = {
            TCP_NewReno.SLOW_START: cwndIncrement_SS,
            TCP_NewReno.CONGESTION_AVOIDANCE: cwndIncrement_CA
        }

        # print("[+]client recev", ACKPidList)
        # ACKPidList.sort()
        for pid in ACKPidList:
            # print("get {} in mode={}".format(pid, self.curTxMode))
            if pid < self.lastACKCounter[0]: # delayed ACK
                continue
            if pid == self.lastACKCounter[0]: # maybe dup ACK
                self.lastACKCounter[1] += 1
            else: # new ack
                self.lastACKCounter = [pid, 1]

                if self.curTxMode in {TCP_NewReno.SLOW_START, TCP_NewReno.CONGESTION_AVOIDANCE}:
                    cwndIncrementFuncDict[self.curTxMode]()
                    self._timeoutUpdate()
                
                elif self.curTxMode == TCP_NewReno.RETRANSMISSION:
                    self.curTxMode = TCP_NewReno.SLOW_START
                
                elif self.curTxMode == TCP_NewReno.FAST_RECOVERY:
                    if pid >= self.high_water:
                    # our retransmission works. Go back to CA
                        self.cwnd = self.ssthresh
                        self.curTxMode = TCP_NewReno.CONGESTION_AVOIDANCE
                        self.cwnd_inc_counter = 0
                    else:
                    # there are still packets missing
                    # decrease cwnd
                    # retransmit the last unACKed packet
                        self.cwnd -= 1
                        self.cwnd = max(self.cwnd, 0) # TODO
                        self.pktToRetransmit += [self.pktInfo_dict[pid+1].toPacket()]
                        
                    self._timeoutUpdate()
                    
                for oldPid in list(self.pktInfo_dict.keys()):
                    if oldPid <= pid:
                        self.pktInfo_dict.pop(oldPid, None)
                        if self.curTxMode == TCP_NewReno.FAST_RECOVERY:
                            self.cwnd -= 1

            if self.lastACKCounter[1] >= 3:
                # triple dup ack
                # go to fast retransmission mode, and stay at Fast Recovery
                self._handleTripleDupACK(
                    lastACKPid=self.lastACKCounter[0],
                    dupACKNum=self.lastACKCounter[1])
            
            # print("LastACKCounter", self.lastACKCounter)
        return

    
    def _getPktsToSend(self):
        """
        send cwnd packets
        """
        pktList = []

        for pkt in self.pktToRetransmit:
            self.pktInfo_dict[pkt.pid] = self._genNewPktInfoFromPkt(pkt)
        pktList += self.pktToRetransmit

        # number of packets to transfer from txbuffer to TCP's tx window
        numOfNewPackets = min(self.cwnd- len(self.pktInfo_dict), len(self.txBuffer))
        numOfNewPackets = max(numOfNewPackets, 0)

        for _ in range(numOfNewPackets):
            # add packets to window
            pkt = self.txBuffer.popleft()
            pkt.txTime = self.time
            pktList.append(pkt)

            if pkt.pid > self.maxPidSent:
                self.maxPidSent = pkt.pid
                self.distincPktsSent += 1

            self.pktInfo_dict[pkt.pid] = self._genNewPktInfoFromPkt(pkt)

        
        self.pktToRetransmit = []

        return pktList
    
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

    def _handleTimeoutPkts(self):
        # Once there is at least one timeout ack, switch to Retransmission mode
        # 

        pidList = list(self.pktInfo_dict.keys())
        pidList.sort()

        # print("cur timeout is ", self.timeout)
        for pid in pidList:
            # print("pkt {} queuingTime {}".format(pid, self.time-self.pktInfo_dict[pid].txTime))
            if self._isPktTimeout(pid):
                if self.verbose:
                    print("[-]Client {uid} @ {time} Pkt {pid} is timeout {queuingTime} >= {timeout}".format(uid=self.suid, time=self.time, pid=pid, queuingTime=self.time-self.pktInfo_dict[pid].txTime, timeout=self.timeout))
                # switch to Retransmission mode 
                # push the packet to buffer (retransmit)
                # update timeout, cwnd, ssthresh
                if self.curTxMode != TCP_NewReno.RETRANSMISSION: # shrink ssthresh only once
                    self.ssthresh = self.cwnd //2

                if self.verbose:
                    print("retransmission")
                self.curTxMode = TCP_NewReno.RETRANSMISSION


                self.pktToRetransmit += [self.pktInfo_dict[pid].toPacket()]
                self.pktInfo_dict.pop(pid, None)


                self.cwnd = 1
                self.timeout *= 2

                # self.curTxMode = TCP_NewReno.SLOW_START
    
    def _handleTripleDupACK(self, lastACKPid, dupACKNum):

        # the missing packet is lastACKPid+1
        missPid = lastACKPid+1
        if missPid in self.pktInfo_dict:
            # switch to Fast Retransmission mode
            # send the missing packet
            # update cwnd and ssthresh
            if self.curTxMode == TCP_NewReno.FAST_RECOVERY:
                pass
            else:
                self.pktToRetransmit += [self.pktInfo_dict[missPid].toPacket()]
                self.ssthresh = max(self.cwnd//2, 1)
                self.cwnd = self.ssthresh+3
                self.high_water = self.maxPidSent
                self._timeoutUpdate()
                # switch to Fast Recovery
                self.curTxMode = TCP_NewReno.FAST_RECOVERY
            
            if self.verbose:
                print("fast recovery")
                print("cwnd={}, sshthresh={}, high_water={}".format(self.cwnd, self.ssthresh, self.high_water))
        return 
    
    
    
    