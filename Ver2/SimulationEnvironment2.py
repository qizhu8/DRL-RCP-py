"""
Different from the scenario in SimulationEnvironment.py, all protocols to be evaluated are not going to compete with each other. At a time only the one protocol is going to be tested.
"""

import numpy as np
from tabulate import tabulate
import matplotlib.pyplot as plt
import pickle as pkl

from application import EchoClient, EchoServer
from channel import SingleModeChannel


alpha = 0.5     # fairness on small values
beta1 = 10      # emphasis on delivery
beta2 = 10      # emphasis on delay
utilityCalcHandlerParams = {"alpha":alpha, "beta1":beta1, "beta2":beta2}



client1 = EchoClient(clientId=1, serverId=11, 
    protocolName="UDP", transportParam={}, 
    trafficMode="periodic", trafficParam={"period":10, "pktsPerPeriod":100}, 
    verbose=False)
server1 = EchoServer(serverId=11, ACKMode=None, verbose=False)

client2 = EchoClient(clientId=2, serverId=12, 
    protocolName="UDP", transportParam={}, 
    trafficMode="periodic", trafficParam={"period":2, "pktsPerPeriod":1}, 
    verbose=False)
server2 = EchoServer(serverId=12, ACKMode=None, verbose=False)


env_clients = [client1, client2]
env_servers = [server1, server2]




"""
Protocols to compare
"""
client_RL = EchoClient(clientId=101, serverId=111, 
    protocolName="mcp", transportParam={"maxTxAttempts":10, "timeout":30, "maxPktTxDDL":1000,
    "beta1":beta1, "beta2":beta2, "alpha":alpha, # alpha-fairness beta1: emphasis on delivery, beta2: emphasis on delay
    "gamma":0.9 }, 
    trafficMode="periodic", trafficParam={"period":4, "pktsPerPeriod":3}, 
    verbose=False)
server_RL = EchoServer(serverId=111, ACKMode="SACK", verbose=False)

client_ARQ = EchoClient(clientId=201, serverId=211, 
    protocolName="window arq", transportParam={"cwnd": 4, "maxTxAttempts":-1, "timeout":30, "maxPktTxDDL":-1, "ACKMode": "LC"}, 
    trafficMode="periodic", trafficParam={"period":4, "pktsPerPeriod":3},
    verbose=False)
server_ARQ = EchoServer(serverId=211, ACKMode="LC", verbose=False)

client_UDP = EchoClient(clientId=301, serverId=311, 
    protocolName="UDP", transportParam={}, 
    trafficMode="periodic", trafficParam={"period":4, "pktsPerPeriod":3}, 
    verbose=False)
server_UDP = EchoServer(serverId=311, ACKMode=None, verbose=False)

client_TCP_Reno = EchoClient(clientId=401, serverId=411,
    protocolName="tcp_newreno", transportParam={"timeout":30, "IW":4}, # IW=2 if SMSS>2190, IW=3 if SMSS>3, else IW=4
    trafficMode="periodic", trafficParam={"period":4, "pktsPerPeriod":3}, 
    verbose=False)
server_TCP_Reno = EchoServer(serverId=411, ACKMode="LC", verbose=False)

# test_clients = [client_RL]
# test_servers = [server_RL]
test_clients = [client_RL, client_UDP, client_ARQ, client_TCP_Reno]
test_servers = [server_RL, server_UDP, server_ARQ, server_TCP_Reno]

channel = SingleModeChannel(processRate=3, bufferSize=50, pktDropProb=0.01, verbose=False)


def test_client(client, server):
    # system time
    simulationPeriod = int(200000) # unit ticks / time slots

    clientList = env_clients + [client]
    serverList = env_servers + [server]

    ACKPacketList = []
    packetList_enCh = []
    packetList_deCh = []

    # clear each client server
    for client, server in zip(clientList, serverList):
        client.transportObj.instance.time = -1
        client.pid = 0
        client.time = -1
        server.time = -1

    channel._initBuffer()

    for time in range(1, simulationPeriod):

        ACKPacketList = []
        # step 1: each server processes remaining pkts 
        for serverId in np.random.permutation(len(serverList)):
            ACKPacketList += serverList[serverId].ticking(packetList_deCh)

        # step 2: clients generate packets
        packetList_enCh = []
        # for client in clientSet:
        for clientId in np.random.permutation(len(clientList)):
            packetList_enCh += clientList[clientId].ticking(ACKPacketList)

        # step 3: feed packets to channel
        # ACKPacketList += channel.putPackets(packetList_enCh) # allow channel feedback 
        channel.putPackets(packetList_enCh)

        # step 3: get packets from channel
        packetList_deCh = channel.getPackets()

        server.recordPerfInThisTick(client.getDistinctPktSent(), 
        utilityCalcHandler=client.transportObj.instance.calcUtility,
        utilityCalcHandlerParams=utilityCalcHandlerParams)

        if time % (simulationPeriod//10) == 0:
            print("time ", time, " =================")
            print("RTT", client.transportObj.instance.SRTT)
            server.printPerf(client.getDistinctPktSent(), client.getProtocolName())

# test each pair of client and server

for client, server in zip(test_clients, test_servers):
    test_client(client, server)

"""
check contents, performance ....
"""
header = ["protocol", "pkts generated", "pkts sent", "pkts delivered", "delivery percentage", "avg delay", "utility per pkt", "overall utility"]
table = []

deliveredPktsPerSlot = dict()

for client, server in zip(test_clients, test_servers): # ignore the first two 
    # for display
    deliveredPkts, deliveryRate, avgDelay = server.serverSidePerf(client.getDistinctPktSent())
    table.append([client.getProtocolName(),
        client.pid,
        client.getDistinctPktSent(),
        deliveredPkts, 
        deliveryRate*100, 
        avgDelay,
        client.transportObj.instance.calcUtility(
            deliveryRate=deliveryRate, avgDelay=avgDelay, deliveredPkts=1, 
            alpha=alpha, beta1=beta1, beta2=beta2),
        client.transportObj.instance.calcUtility(
            deliveryRate=deliveryRate, avgDelay=avgDelay, deliveredPkts=deliveredPkts, 
            alpha=alpha, beta1=beta1, beta2=beta2)
    ])
    # for plot
    deliveredPktsPerSlot[client.getProtocolName()] = [server.pktsPerTick, server.perfRecords]

deliveredPktsPerSlot["general"] = table
deliveredPktsPerSlot["header"] = header
print(tabulate(table, headers=header))

# store data

with open('perfData2.pkl', 'wb') as handle:
    pkl.dump(deliveredPktsPerSlot, handle, protocol=pkl.HIGHEST_PROTOCOL)