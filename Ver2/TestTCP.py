import numpy as np

from application import EchoClient, EchoServer
from channel import SingleModeChannel

client1 = EchoClient(clientId=1, serverId=11, 
    protocolName="UDP", transportParam={}, 
    trafficMode="periodic", trafficParam={"period":4, "pktsPerPeriod":0}, 
    verbose=False)
server1 = EchoServer(serverId=11, ACKMode=None, verbose=False)

client2 = EchoClient(clientId=2, serverId=11, 
    protocolName="UDP", transportParam={}, 
    trafficMode="periodic", trafficParam={"period":2, "pktsPerPeriod":1}, 
    verbose=False)
server2 = EchoServer(serverId=12, ACKMode=None, verbose=False)


"""
Protocols to compare
"""

client_TCP_Reno = EchoClient(clientId=401, serverId=411,
    protocolName="tcp_newreno", transportParam={"timeout":30, "IW":4}, # IW=2 if SMSS>2190, IW=3 if SMSS>3, else IW=4
    trafficMode="periodic", trafficParam={"period":1, "pktsPerPeriod":3}, 
    verbose=True
    )
server_TCP_Reno = EchoServer(serverId=411, ACKMode="LC", verbose=True)

clientList = [client1, client2, client_TCP_Reno]
serverList = [server1, server2, server_TCP_Reno]

channel = SingleModeChannel(processRate=3, bufferSize=100, pktDropProb=0.01, verbose=False)


# system time
simulationPeriod = int(1000) # unit ticks / time slots
ACKPacketList = []
packetList_enCh = []
packetList_deCh = []

for time in range(1, simulationPeriod):


    # step 1: clients generate packets
    packetList_enCh = []
    # for client in clientSet:
    for clientId in np.random.permutation(len(clientList)):
        packetList_enCh += clientList[clientId].ticking(ACKPacketList)
    ACKPacketList = []

    # step 2: feed packets to channel
    ACKPacketList += channel.putPackets(packetList_enCh)

    # step 3: get packets from channel
    packetList_deCh = channel.getPackets()

    # step 4: each server get what they need from the channel
    for serverId in np.random.permutation(len(serverList)):
        ACKPacketList += serverList[serverId].ticking(packetList_deCh)

    if time % 100 == 0:
        print("time ", time)
        for client, server in zip(clientList, serverList):
            server.printPerf(client.getDistinctPktSent(), client.getProtocolName())

for client, server in zip(clientList, serverList):
    server.printPerf(client.getDistinctPktSent(), client.getProtocolName())