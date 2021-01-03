from Applications import SimpleServer, SimpleClient
from channel import SingleModeChannel

"""
    Initialize Environments

    Note that user id, including clientId and serverId, should be distinct.
"""

#client 1 sends to server 1
client1 = SimpleClient(clientId=1, serverId=2, timeout=3, appMode="window arq", param={"cwnd":2, "ACKMode":"LC"}, verbose=True)
server1 = SimpleServer(serverId=2, ACKMode="LC", verbose=True)

# client 2 sends to server 2
client2 = SimpleClient(clientId=3, serverId=4, appMode="periodic", param={"period":3, "pktsPerPeriod": 4, "offset": 5, "ACKMode": None}, verbose=True)
server2 = SimpleServer(serverId=4, ACKMode="SACK", verbose=True)


clientSet = {client1, client2}
serverSet = {server1, server2}
channel = SingleModeChannel(processRate=1, bufferSize=10, pktDropProb=0)

# system time
simulationPeriod = 100 # unit ticks / time slots
ACKPacketList = []
packetList_enCh = []
packetList_deCh = []

for time in range(simulationPeriod):
    print("="*40)
    print("time = %d" % time)

    # step 1: clients generate packets
    packetList_enCh = []
    for client in clientSet:
        flag, _packetList = client.ticking(ACKPacketList)
        packetList_enCh += _packetList
    ACKPacketList = []

    # step 2: feed packets to channel
    channel.putPackets(packetList_enCh)

    # step 3: get packets from channel
    packetList_deCh = channel.getPackets()


    # step 4: each server get what they need from the channel
    for server in serverSet:
        flag, _ACKPackets = server.ticking(packetList_deCh)
        ACKPacketList += _ACKPackets


