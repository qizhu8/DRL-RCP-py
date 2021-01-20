import numpy as np
from tabulate import tabulate
import matplotlib.pyplot as plt
import pickle as pkl

from application import EchoClient, EchoServer
from channel import SingleModeChannel



alpha = 0.5     # fairness on small values
beta1 = 0.1    # emphasis on delivery
beta2 = 1      # emphasis on delay
utilityCalcHandlerParams = {"alpha":alpha, "beta1":beta1, "beta2":beta2}

client1 = EchoClient(clientId=1, serverId=11, 
    protocolName="UDP", transportParam={}, 
    trafficMode="periodic", trafficParam={"period":10, "pktsPerPeriod":50}, 
    verbose=False)
server1 = EchoServer(serverId=11, ACKMode=None, verbose=False)

client2 = EchoClient(clientId=2, serverId=12, 
    protocolName="UDP", transportParam={}, 
    trafficMode="periodic", trafficParam={"period":2, "pktsPerPeriod":1}, 
    verbose=False)
server2 = EchoServer(serverId=12, ACKMode=None, verbose=False)







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

clientList = [client1, client2, client_RL, client_UDP, client_ARQ, client_TCP_Reno]
serverList = [server1, server2, server_RL, server_UDP, server_ARQ, server_TCP_Reno]

channel = SingleModeChannel(processRate=3, bufferSize=50, pktDropProb=0.01, verbose=False)


# system time
simulationPeriod = int(20000) # unit ticks / time slots
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
    # ACKPacketList += channel.putPackets(packetList_enCh) # allow channel feedback 
    channel.putPackets(packetList_enCh)

    # step 3: get packets from channel
    packetList_deCh = channel.getPackets()

    # step 4: each server get what they need from the channel
    for serverId in np.random.permutation(len(serverList)):
        ACKPacketList += serverList[serverId].ticking(packetList_deCh)



    if time % 100 == 0:
        print("time ", time, " =================")

        for client, server in zip(clientList, serverList):
            server.printPerf(client.getDistinctPktSent(), client.getProtocolName())

for client, server in zip(clientList, serverList):
    server.printPerf(client.getDistinctPktSent(), client.getProtocolName())

"""
check contents, performance ....
"""
header = ["protocol", "pkts generated", "pkts sent", "pkts delivered", "delivery rate", "avg delay", "utility per pkt", "sum utility"]
table = []

deliveredPktsPerSlot = dict()

for client, server in zip(clientList[2:], serverList[2:]): # ignore the first two 
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
    deliveredPktsPerSlot[client.getProtocolName()] = [server.pktsPerTick]

deliveredPktsPerSlot["utilityParam"] = utilityCalcHandlerParams
deliveredPktsPerSlot["general"] = table
deliveredPktsPerSlot["header"] = header
print(tabulate(table, headers=header))

# store data

with open('perfData.pkl', 'wb') as handle:
    pkl.dump(deliveredPktsPerSlot, handle, protocol=pkl.HIGHEST_PROTOCOL)