import numpy as np

from packet import Packet
from protocols.window_arq_v2 import Window_ARQ

pkt1 = Packet(pid=1, suid=0, duid=1)
pkt2 = Packet(pid=2, suid=0, duid=1)
pkt3 = Packet(pid=3, suid=0, duid=1)

arq = Window_ARQ(suid=0, duid=1, params={"ACKMode": "SACK", "cwnd":2}, verbose=True)

# the second pkt2 should trigger a warning
# the pkt3 should trigger a full-window warning
arq.window.pushPkts(curTime=1, pktList=[pkt1, pkt2, pkt2, pkt3]) 

# only packet 1 is removed
arq.window.ACKPkts_SACK([1, 3])
arq.window.pushPkts(curTime=1, pktList=[pkt3]) 

# remove pkt 2 and 3
arq.window.ACKPkts_LC(3)

# even though two pkt2 are pushed, only the first should remain
pkt2_2 = Packet(pid=2, suid=0, duid=1)
pkt2_2.txTime = 100
arq.window.pushPkts(curTime=1, pktList=[pkt2, pkt2_2, pkt3])
print(arq.window)


infARQ = Window_ARQ(suid=0, duid=1, params={"ACKMode": "SACK", "cwnd":-1}, verbose=True)

for i in range(100):
    pkt1 = Packet(pid=i, suid=0, duid=1)
    infARQ.window.pushPkts(curTime=i, pktList = [pkt1])

print(infARQ.window.bufferSize())