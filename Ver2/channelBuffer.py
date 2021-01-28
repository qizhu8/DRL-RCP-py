import sys
from collections import deque
from packet  import Packet

class ChannelBuffer(object):
    """
        ChannelBuffer maintains a FIFO queue. 

                            -------------
       <- deque (popleft)   |-| |-|       <- enque (append)
                            -------------
        
        If the buffer is full, it will no long accept packets

        When a packet enters the buffer, the enque time is also stored.
        The packet won't exit until its retention time in buffer >= rtt.
    """

    def __init__(self, bufferSize=0, rtt=0):

        
        self.bufferSize = 0 if bufferSize < 0 else bufferSize

        self.rtt = rtt

        self.numPacketsInBuffer = 0
        self.FIFOQueue = deque(maxlen=self.bufferSize)
        self.timeQueue = deque(maxlen=self.bufferSize) # used to store the enque time of each packet
    
    def isFull(self):
        """check whether the channel can still accept packets"""
        return self.bufferSize > 0 and self.numPacketsInBuffer >= self.bufferSize


    def size(self):
        return self.numPacketsInBuffer

    def enqueue(self, packet , time=0):
        """
        userId is the host that sends the packet.
        It may not be the same as the source of the packet
        """
        if self.isFull():
            return False

        self.FIFOQueue.append(packet)
        self.timeQueue.append(time)

        self.numPacketsInBuffer += 1

        return True
    
    def dequeue(self, time=-sys.maxsize):
        if len(self.FIFOQueue) and (time-self.timeQueue[0]) >= self.rtt:
            _packet = self.FIFOQueue.popleft()
            _ = self.timeQueue.popleft()

            self.numPacketsInBuffer -= 1

            return True, _packet
        return False, []
    
            

if __name__ == "__main__":

    buffer = ChannelBuffer(bufferSize=3, rtt=2)

    buffer.enqueue(packet=Packet(pid=0, duid=88), time=0)
    buffer.enqueue(packet=Packet(pid=1, duid=88), time=1)
    buffer.enqueue(packet=Packet(pid=2, duid=88), time=1)
    buffer.enqueue(packet=Packet(pid=3, duid=88), time=2) # expect a full buffer -> drop packet
    flag, packet = buffer.dequeue(time=2) # expect to see packet 0
    if flag:
        print(packet)
    else:
        print("err")
    
    print("at time 3")
    while True:
        flag, packet = buffer.dequeue(3) # expect to see packet 0, 1, 2, but not 3
        if flag:
            print(packet)
        else:
            print("no more packet")
            break