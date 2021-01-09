import numpy as np

from application import EchoClient, EchoServer
from channel import SingleModeChannel

client1 = EchoClient(clientId=1, serverId=11, 
    protocolName="UDP", transportParam={}, 
    trafficMode="periodic", trafficParam={"period":2, "pktsPerPeriod":1}, 
    verbose=False)
server1 = EchoServer(serverId=11, ACKMode=None, verbose=False)

client2 = EchoClient(clientId=2, serverId=12, 
    protocolName="window arq", transportParam={"cwnd": 4, "maxTxAttempts":-1, "timeout":4, "maxPktTxDDL":100, "ACKMode": "LC"}, 
    trafficMode="poisson", trafficParam={"lambda":4}, 
    verbose=False)
server2 = EchoServer(serverId=12, ACKMode="LC", verbose=False)



client_RL = EchoClient(clientId=301, serverId=311, 
    protocolName="mcp", transportParam={"maxTxAttempts":-1, "timeout":30, "maxPktTxDDL":100,
    "beta1":10, "beta2":1, "alpha":0.1, # alpha-fairness beta1: emphasis on delivery, beta2: emphasis on delay
    "gamma":0.9 }, 
    trafficMode="periodic", trafficParam={"period":4, "pktsPerPeriod":2}, 
    verbose=True)
server_RL = EchoServer(serverId=311, ACKMode="SACK", verbose=True)

clientList = [client1, client2, client_RL]
serverList = [server1, server2, server_RL]

channel = SingleModeChannel(processRate=3, bufferSize=100, pktDropProb=0.5, verbose=False)


# system time
simulationPeriod = int(100) # unit ticks / time slots
ACKPacketList = []
packetList_enCh = []
packetList_deCh = []

for time in range(1, simulationPeriod):
    print("time ", time)

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


for client, server in zip(clientList, serverList):
    server.printPerf(client.getDistinctPktSent())