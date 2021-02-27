"""
Different from the scenario in SimulationEnvironment.py, all protocols to be evaluated are not going to compete with each other. At a time only the one protocol is going to be tested.
"""
import sys
from os import path
import numpy as np
from tabulate import tabulate
import matplotlib.pyplot as plt
import pickle as pkl

from application import EchoClient, EchoServer
from channel import SingleModeChannel

if len(sys.argv) > 2:
    beta1 = float(sys.argv[1])
    beta2 = float(sys.argv[2])
else:
    beta1 = 10      # emphasis on delivery
    beta2 = 1      # emphasis on delay

print("beta1={beta1}, beta2={beta2}".format(beta1=beta1, beta2=beta2))

utilityCalcHandlerParams = {"beta1":beta1, "beta2":beta2}
if len(sys.argv) > 3:
    pklFilename = sys.argv[3]
else:
    pklFilename = "perfData2_{beta1}_{beta2}.pkl".format(beta1=beta1, beta2=beta2)

print("results save to \\result\\"+pklFilename)


if len(sys.argv) > 4:
    simulationPeriod = int(sys.argv[4]) # unit ticks / time slots
else:
    simulationPeriod = int(1000) # unit ticks / time slots

"""
add background traffic
"""
env_clients = []
env_servers = []
for clientId in range(1, 4+1):

    client = EchoClient(clientId=clientId, serverId=10+clientId, 
        protocolName="UDP", transportParam={}, 
        trafficMode="periodic", trafficParam={"period":1, "pktsPerPeriod":1}, 
        verbose=False)
    server = EchoServer(serverId=10+clientId, ACKMode=None, verbose=False)
    
    env_clients.append(client)
    env_servers.append(server)






"""
Protocols to compare
"""
client_RL = EchoClient(clientId=101, serverId=111, 
    protocolName="mcp", transportParam={"maxTxAttempts":-1, "timeout":30, "maxPktTxDDL":-1,
    "beta1":beta1, "beta2":beta2, # beta1: emphasis on delivery, beta2: emphasis on delay
    "gamma":0.9,
    "learnRetransmissionOnly": True}, # whether only learn the data related to retransmission
    trafficMode="periodic", trafficParam={"period":1, "pktsPerPeriod":1}, 
    verbose=False)
server_RL = EchoServer(serverId=111, ACKMode="SACK", verbose=False)

client_ARQ_finit = EchoClient(clientId=201, serverId=211, 
    protocolName="window arq", transportParam={"cwnd": 140, "maxTxAttempts":-1, "timeout":30, "maxPktTxDDL":-1, "ACKMode": "SACK"}, 
    trafficMode="periodic", trafficParam={"period":1, "pktsPerPeriod":1},
    verbose=False)
server_ARQ_finit = EchoServer(serverId=211, ACKMode="SACK", verbose=False)

client_ARQ_infinit_cwnd = EchoClient(clientId=301, serverId=311, 
    protocolName="window arq", transportParam={"cwnd": -1, "maxTxAttempts":-1, "timeout":30, "maxPktTxDDL":-1, "ACKMode": "SACK"}, 
    trafficMode="periodic", trafficParam={"period":1, "pktsPerPeriod":1},
    verbose=False)
server_ARQ_infinit_cwnd = EchoServer(serverId=311, ACKMode="SACK", verbose=False)

client_UDP = EchoClient(clientId=401, serverId=411, 
    protocolName="UDP", transportParam={}, 
    trafficMode="periodic", trafficParam={"period":1, "pktsPerPeriod":1}, 
    verbose=False)
server_UDP = EchoServer(serverId=411, ACKMode=None, verbose=False)

# client_TCP_Reno = EchoClient(clientId=401, serverId=411,
#     protocolName="tcp_newreno", transportParam={"timeout":30, "IW":4}, # IW=2 if SMSS>2190, IW=3 if SMSS>3, else IW=4
#     trafficMode="periodic", trafficParam={"period":1, "pktsPerPeriod":2}, 
#     verbose=False)
# server_TCP_Reno = EchoServer(serverId=411, ACKMode="LC", verbose=False)

# test_clients = [client_UDP]
# test_servers = [server_UDP]
# test_clients = [client_ARQ_finit]
# test_servers = [server_ARQ_finit]
# test_clients = [client_RL]
# test_servers = [server_RL]
# test_clients = [client_RL, client_UDP, client_ARQ, client_TCP_Reno]
# test_servers = [server_RL, server_UDP, server_ARQ, server_TCP_Reno]
test_clients = [client_UDP, client_ARQ_finit, client_ARQ_infinit_cwnd, client_RL]
test_servers = [server_UDP, server_ARQ_finit, server_ARQ_infinit_cwnd, server_RL]

def test_client(client, server):

    serverPerfFilename = client.getProtocolName()+"_perf.pkl"

    if client.getProtocolName().lower() not in {"mcp"}:
        #check whether can load the previous performance file directly
        
        if path.exists(serverPerfFilename):
            print("find file ", serverPerfFilename)
            clientSidePerf, distincPktsSent, clientPid = server.calcPerfBasedOnDataFile(
                serverPerfFilename,
                utilityCalcHandler=client.transportObj.instance.calcUtility,
                utilityCalcHandlerParams=utilityCalcHandlerParams
            )
            
            # hacking
            client.pid = clientPid
            client.transportObj.instance.distincPktsSent = distincPktsSent
            client.transportObj.instance.perfDict = clientSidePerf.copy()
            return


    # system time
    channel = SingleModeChannel(processRate=3, bufferSize=300, rtt=100, pktDropProb=0.1, verbose=False)

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

    while not channel.isFull(): # fill the channel with environment packets
        packetList_enCh = []
        for clientId in np.random.permutation(len(env_clients)):
            packetList_enCh += env_clients[clientId].ticking(ACKPacketList)
        channel.putPackets(packetList_enCh)




    packetList_enCh = []
    for time in range(1, simulationPeriod+1):
        ACKPacketList = []
        # step 1: each server processes remaining pkts 
        for serverId in range(len(serverList)):
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

        if time % 30 == 0: # record performance for the past 30 slots
            server.recordPerfInThisTick(client.getPktGen(), 
                utilityCalcHandler=client.transportObj.instance.calcUtility,
                utilityCalcHandlerParams=utilityCalcHandlerParams)

        if time % (simulationPeriod//10) == 0:
            print("time ", time, " =================")
            print("RTT", client.transportObj.instance.SRTT)
            client.transportObj.instance.clientSidePerf()
            server.printPerf(
                client.getPktGen(),
                client.getProtocolName())
    
    server.storePerf(serverPerfFilename,
        clientPid=client.pid,
        distincPktsSent=client.getPktGen(),
        clientSidePerf=client.transportObj.instance.clientSidePerf())

# test each pair of client and server

for client, server in zip(test_clients, test_servers):
    test_client(client, server)

"""
check contents, performance ....
"""
header = ["ptcl", "pkts gen", "pkts sent", "pkts dlvy", "dlvy perc", "avg dly", "sys util", "l25p dlvy", "l25p dlvy perc", 'l25p dly', "l25p util"]
table = []

deliveredPktsPerSlot = dict()
deliveredPktsPerSlot["protocols"] = []
for client, server in zip(test_clients, test_servers): # ignore the first two 
    deliveredPktsPerSlot["protocols"].append(client.getProtocolName())
    deliveredPktsPerSlot[client.getProtocolName()] = dict()
    
    server.printPerf(client.getPktGen(), client.getProtocolName())
    client.transportObj.instance.clientSidePerf()

    # store data
    deliveredPktsPerSlot[client.getProtocolName()]["serverPerf"] = [server.pktsPerTick, server.delayPerPkt, server.perfRecords]
    deliveredPktsPerSlot[client.getProtocolName()]["clientPerf"] = client.transportObj.instance.clientSidePerf()

    # for display
    deliveredPkts, deliveryRate, avgDelay = server.serverSidePerf(client.getPktGen())
    last25percTime = int(simulationPeriod*0.25)
    last25percPkts = sum(server.pktsPerTick[-last25percTime:])
    last25percDelveyRate = last25percPkts / (client.pktsPerTick*last25percTime)
    if(last25percPkts == 0):
        print(client.getProtocolName(), "have zero packts delivered ")
    last25percDelay = sum(server.delayPerPkt[-last25percPkts:]) / last25percPkts
    last25percUtil = client.transportObj.instance.calcUtility(
            deliveryRate=last25percDelveyRate, avgDelay=last25percDelay,
            beta1=beta1, beta2=beta2)

    table.append([client.getProtocolName(),
        client.pid,
        client.getPktGen(),
        deliveredPkts, 
        deliveryRate*100, 
        avgDelay,
        client.transportObj.instance.calcUtility(
            deliveryRate=deliveryRate, avgDelay=avgDelay,
            beta1=beta1, beta2=beta2),
        last25percPkts,
        last25percDelveyRate,
        last25percDelay,
        last25percUtil
    ])
    
    
    
    

deliveredPktsPerSlot["utilityParam"] = utilityCalcHandlerParams
deliveredPktsPerSlot["general"] = table
deliveredPktsPerSlot["header"] = header
print(tabulate(table, headers=header))

# store data
with open("results/"+pklFilename, 'wb') as handle:
    pkl.dump(deliveredPktsPerSlot, handle, protocol=pkl.HIGHEST_PROTOCOL)
print("save to ", pklFilename)

# plot MCP packet ignored time diagram
plt.plot(client_RL.transportObj.instance.pktIgnoredCounter, label="MCP")
plt.savefig("results/MCP_pktignore_{beta1}_{beta2}.png".format(beta1=beta1, beta2=beta2))

np.set_printoptions(suppress=True)
csvFileName="results/MCP_RL_perf_{beta1}_{beta2}.csv".format(beta1=beta1, beta2=beta2)
np.savetxt(csvFileName, client_RL.transportObj.instance.RL_Brain.memory, delimiter=",", fmt='%f')
