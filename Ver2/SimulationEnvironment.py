import numpy as np

from application import EchoClient, EchoServer
from channel import SingleModeChannel

client1 = EchoClient(clientId=1, serverId=11, 
    protocolName="UDP", transportParam={}, 
    trafficMode="periodic", trafficParam={"period":4, "pktsPerPeriod":100}, 
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
client_RL = EchoClient(clientId=101, serverId=111, 
    protocolName="mcp", transportParam={"maxTxAttempts":-1, "timeout":30, "maxPktTxDDL":-1,
    "beta1":10, "beta2":1, "alpha":0.1, # alpha-fairness beta1: emphasis on delivery, beta2: emphasis on delay
    "gamma":0.9 }, 
    trafficMode="periodic", trafficParam={"period":4, "pktsPerPeriod":2}, 
    verbose=False)
server_RL = EchoServer(serverId=111, ACKMode="SACK", verbose=False)

client_ARQ = EchoClient(clientId=201, serverId=211, 
    protocolName="window arq", transportParam={"cwnd": 40, "maxTxAttempts":-1, "timeout":30, "maxPktTxDDL":-1, "ACKMode": "LC"}, 
    trafficMode="periodic", trafficParam={"period":4, "pktsPerPeriod":2},
    verbose=False)
server_ARQ = EchoServer(serverId=211, ACKMode="LC", verbose=False)

client_UDP = EchoClient(clientId=301, serverId=311, 
    protocolName="UDP", transportParam={}, 
    trafficMode="periodic", trafficParam={"period":4, "pktsPerPeriod":2}, 
    verbose=False)
server_UDP = EchoServer(serverId=311, ACKMode=None, verbose=False)

clientList = [client1, client2, client_RL, client_ARQ, client_UDP]
serverList = [server1, server2, server_RL, server_ARQ, server_UDP]

channel = SingleModeChannel(processRate=3, bufferSize=100, pktDropProb=0.5, verbose=False)


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