from applications import SimpleServer, SimpleClient
from channel import SingleModeChannel
from MCP_Client import MCP_Client
import numpy as np
"""
    Initialize Environments

    Note that user id, including clientId and serverId, should be distinct.
"""

#client 1 sends to server 1
# client1 = SimpleClient(clientId=1, serverId=2, timeout=3, appMode="window arq", param={"cwnd":2, "ACKMode":"LC"}, verbose=False)
# server1 = SimpleServer(serverId=2, ACKMode="LC", verbose=False)
client1 = SimpleClient(clientId=1, serverId=4, appMode="periodic", param={"period":1, "pktsPerPeriod": 1, "offset": 5, "ACKMode": None}, verbose=False)
server1 = SimpleServer(serverId=2, ACKMode=None , verbose=False)

# client 2 sends to server 2
client2 = SimpleClient(clientId=3, serverId=4, appMode="periodic", param={"period":3, "pktsPerPeriod": 10, "offset": 3, "ACKMode": None}, verbose=False)
server2 = SimpleServer(serverId=4, ACKMode=None , verbose=False)




# pure udp player
client_UDP = SimpleClient(clientId=100, serverId=101, appMode="periodic", param={"period":3, "pktsPerPeriod": 4, "offset": 3, "ACKMode": None}, verbose=False)
server_UDP = SimpleServer(serverId=101, ACKMode=None , verbose=False)

# ARQ player
client_ARQ = SimpleClient(clientId=200, serverId=201, timeout=30, appMode="window arq", param={"cwnd":40, "pktsPerPeriod": 4, "offset": 3, "ACKMode": "LC"}, verbose=False)
server_ARQ = SimpleServer(serverId=201, ACKMode="LC", verbose=False)

client_RL = MCP_Client(clientId=300, serverId=301, timeout=30, 
    beta1=1, beta2=0.1,
    param={"period":3, "pktsPerPeriod": 4, "offset": 3, "ACKMode": None}, verbose=False)
server_RL = SimpleServer(serverId=301, verbose=False, ACKMode="SACK") # must be SACK


clientList = [client1, client2, client_UDP, client_ARQ, client_RL]
serverList = [server1, server2, server_UDP, server_ARQ, server_RL]


channel = SingleModeChannel(processRate=10, bufferSize=100, pktDropProb=0.1, verbose=False)

# system time
simulationPeriod = int(10000) # unit ticks / time slots
ACKPacketList = []
packetList_enCh = []
packetList_deCh = []

for time in range(1, simulationPeriod):
    # print("time ", time)

    # step 1: clients generate packets
    packetList_enCh = []
    # for client in clientSet:
    for clientId in np.random.permutation(len(clientList)):
        flag, _packetList = clientList[clientId].ticking(ACKPacketList)
        packetList_enCh += _packetList
    ACKPacketList = []

    # step 2: feed packets to channel
    channel.putPackets(packetList_enCh)

    # step 3: get packets from channel
    packetList_deCh = channel.getPackets()

    # step 4: each server get what they need from the channel
    for serverId in np.random.permutation(len(serverList)):
        flag, _ACKPackets = serverList[serverId].ticking(packetList_deCh)
        ACKPacketList += _ACKPackets
    if time % 500 == 0:
        print("===="*20)
        print("time: ",time)
        print("-----UDP-----")
        server_UDP.printPerf(client_UDP.pid-1)
        print("-----ARQ-----")
        server_ARQ.printPerf(client_ARQ.pid-1)
        print("-----RL-----")
        server_RL.printPerf(client_RL.pid-1)
        client_RL.printPerf()

print("===="*20)
print("time: ",time)
print("-----UDP-----")
server_UDP.printPerf(client_UDP.pid-1)
print("client pkts sent", client_UDP.pid)
print("-----ARQ-----")
server_ARQ.printPerf(client_ARQ.pid-1)
print("client pkts sent", client_ARQ.pid)
print("-----RL-----")
server_RL.printPerf(client_RL.pid-1)
print("client pkts sent", client_RL.pid)
client_RL.printPerf()
print("beta1:", client_RL.alphaFairness_beta1)
print("beta2:", client_RL.alphaFairness_beta2)

"""
check contents
"""
print("\n"*3)

deliveriedPkts, deliveryRate, avgDelay = server_UDP.serverSidePerf(client_UDP.pid-1)
print("UDP: {}\t{}\t{:.2f}\t{:.2f}".format(client_UDP.pid, deliveriedPkts, deliveryRate*100, avgDelay))
deliveriedPkts, deliveryRate, avgDelay = server_ARQ.serverSidePerf(client_ARQ.pid-1)
print("ARQ: {}\t{}\t{:.2f}\t{:.2f}".format(client_ARQ.pid, deliveriedPkts, deliveryRate*100, avgDelay))
deliveriedPkts, deliveryRate, avgDelay = server_RL.serverSidePerf(client_RL.pid-1)
print("MCP: {}\t{}\t{:.2f}\t{:.2f}\t{}".format(client_RL.pid, deliveriedPkts, deliveryRate*100, avgDelay, client_RL.retransPkts))