# from queue import PriorityQueue, Queue
from collections import deque
from packet  import Packet

class ChannelBuffer(object):
    """
        ChannelBuffer maintains a FIFO queue. 

                            -------------
       <- deque (popleft)   |-| |-|       <- enque (append)
                            -------------
    """

    def __init__(self, bufferSize=0, logOn=False):

        
        self.bufferSize = 0 if bufferSize < 0 else bufferSize

        self.numPacketsInBuffer = 0
        self.FIFOQueue = deque(maxlen=self.bufferSize)

        # init log
        self.logOn = logOn
        self.initLog()
    
    def isFull(self):
        """check whether the channel can still accept packets"""
        return self.bufferSize > 0 and self.numPacketsInBuffer >= self.bufferSize


    def size(self):
        return self.numPacketsInBuffer

    def enqueue(self, packet, userId=0 , time=0):
        """
        userId is the host that sends the packet.
        It may not be the same as the source of the packet
        """
        if self.isFull():
            # log packet drop event
            self.logDrop(userId, time)
            
            return False

        self.FIFOQueue.append(packet)
        self.numPacketsInBuffer += 1

        # log packet enqueue event
        self.logEnqueue(userId, time)
        
        return True
    
    def dequeue(self, time=0):
        if len(self.FIFOQueue):
            _packet = self.FIFOQueue.popleft()
            self.numPacketsInBuffer -= 1

            # log packet dequeue event
            self.logDequeue(time)

            return True, _packet
        return False, []
    

    """
    logging related function
    """
    def initLog(self):
        self.userProfile = dict()
        self.userIdQueue = deque(maxlen=self.bufferSize)
        if self.logOn:
            self.log = list()
            
    
    def getLog(self):
        if self.logOn:
            return self.log
        return []

    def logDrop(self, userId, time=0):
        if self.logOn:
            self.log.append([time, 'd', userId, self.numPacketsInBuffer])
            self.userProfile[userId][3] += 1

    def logEnqueue(self, userId, time=0):
        if userId not in self.userProfile:
            # create profile item
            # [packetsInBuffer, enqueueAttempts, dequeueAttempts, dropPackets]
            self.userProfile[userId] = [0, 0, 0, 0] # 

        self.userProfile[userId][0] += 1
        self.userProfile[userId][1] += 1
        self.userIdQueue.append(userId)
        if self.logOn:
            self.log.append([time, '+', userId, self.numPacketsInBuffer])
    
    def logDequeue(self, time=0):
        userId = self.userIdQueue.popleft()
        self.userProfile[userId][0] -= 1
        self.userProfile[userId][2] += 1
        if self.logOn:
            self.log.append([time, '-', userId, self.numPacketsInBuffer])
    
    def logPrint(self):
        if self.logOn:
            for item in self.log:
                print("{time}\t{tag}\t{userId}\t{size}".format(time=item[0], tag=item[1], userId=item[2], size=item[3]))

    def getProfile(self):
        return self.userProfile

    def __str__(self):
        template = "userId:{userId}\tinBuf:{packetsInBuf}\tenque:{enqueueNum}\tdeque:{dequeueNum}\tdrop:{dropNum}"
        # s = "userId\tpacketsInBuf\tenqueueNum\tdequeueNum\tdropNum"
        s = ""

        users = list(self.userProfile.keys())
        users.sort()
        for userId in users:
            s += "\n"
            s += template.format(userId=userId,
            packetsInBuf=self.userProfile[userId][0],
            enqueueNum=self.userProfile[userId][1],
            dequeueNum=self.userProfile[userId][2],
            dropNum=self.userProfile[userId][3]
            )
        return s

if __name__ == "__main__":

    buffer = ChannelBuffer(bufferSize=3)

    buffer.enqueue(userId=1, packet=Packet(pid=0, duid=88))
    buffer.enqueue(userId=2, packet=Packet(pid=0, duid=88))
    buffer.enqueue(userId=1, packet=Packet(pid=1, duid=88))
    buffer.enqueue(userId=1, packet=Packet(pid=2, duid=88)) # expect a full buffer -> drop packet
    flag, packet = buffer.dequeue(1) # expect to see packet 0
    if flag:
        print(packet)
    else:
        print("err")
    
    flag, packet = buffer.dequeue(3) # expect to see error
    if flag:
        print(packet)
    else:
        print("err")
    
    buffer.logPrint()
    print(buffer)