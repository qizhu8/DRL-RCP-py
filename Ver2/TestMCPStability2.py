"""
In this simulation, we allow multiple protocols existing simultaneously. We would like to see whether MCP is so aggresive that it pushed all other protocols to receive no throughput.
"""
import sys
from os import path
import numpy as np
from tabulate import tabulate
import matplotlib.pyplot as plt
import pickle as pkl

from application import EchoClient, EchoServer
from channel import SingleModeChannel

if len(sys.argv) > 3:
    alpha = int(sys.argv[1])
    beta1 = float(sys.argv[2])
    beta2 = float(sys.argv[3])
else:
    alpha = 2       # quadratic 
    beta1 = 0.8     # emphasis on delivery
    beta2 = 0.2     # emphasis on delay

alpha = np.round(alpha, 2)

print("beta1={beta1}, beta2={beta2}".format(beta1=beta1, beta2=beta2))

utilityCalcHandlerParams = {"beta1":beta1, "beta2":beta2, "alpha":alpha}
if len(sys.argv) > 4:
    pklFilename = sys.argv[4]
else:
    pklFilename = "perfData2_{alpha}_{beta1}_{beta2}.pkl".format(alpha=alpha, beta1=beta1, beta2=beta2)

print("results save to \\result\\"+pklFilename)


if len(sys.argv) > 5:
    simulationPeriod = int(sys.argv[5]) # unit ticks / time slots
else:
    simulationPeriod = int(10000) # unit ticks / time slots







"""
add background traffic
"""
# only use to fullfill the channel when the channel begins
bgclient = EchoClient(clientId=9998, serverId=9999, 
        protocolName="UDP", transportParam={}, 
        trafficMode="periodic", trafficParam={"period":1, "pktsPerPeriod":1}, 
        verbose=False)




def test_channel(processRate=3, recordingPeriod=30):
    """
    processRate: channel process rate
    recordingPeriod: how often to note down the number of delivered packets for each client-server
    """
    throughputDetail = [] # record the throughput of each server in each recording period
    ignored_pkt, retrans_pkt, retransProb = 0, 0, 0

    # system time
    channel = SingleModeChannel(processRate=processRate, bufferSize=300, rtt=10, pktDropProb=0.1, verbose=False)

    clientList, serverList = [], []
    for clientId in range(1, 2+1):

        client = EchoClient(clientId=clientId, serverId=10+clientId, 
            protocolName="UDP", transportParam={}, 
            trafficMode="periodic", trafficParam={"period":1, "pktsPerPeriod":1}, 
            verbose=False)
        server = EchoServer(serverId=10+clientId, ACKMode=None, verbose=False)

        clientList.append(client)
        serverList.append(server)

    client_RL = EchoClient(clientId=101, serverId=111, 
        protocolName="mcp", transportParam={"maxTxAttempts":-1, "timeout":30, "maxPktTxDDL":-1,
        "alpha":alpha,
        "beta1":beta1, "beta2":beta2, # beta1: emphasis on delivery, beta2: emphasis on delay
        "gamma":0.9,
        "learnRetransmissionOnly": True}, # whether only learn the data related to retransmission
        trafficMode="periodic", trafficParam={"period":1, "pktsPerPeriod":1}, 
        verbose=False)
    server_RL = EchoServer(serverId=111, ACKMode="SACK", verbose=False)
    clientList.append(client_RL)
    serverList.append(server_RL)

    client_ARQ_infinit_cwnd = EchoClient(clientId=301, serverId=311, 
        protocolName="window arq", transportParam={"cwnd": -1, "maxTxAttempts":-1, "timeout":30, "maxPktTxDDL":-1, "ACKMode": "SACK"}, 
        trafficMode="periodic", trafficParam={"period":1, "pktsPerPeriod":1},
        verbose=False)
    server_ARQ_infinit_cwnd = EchoServer(serverId=311, ACKMode="SACK", verbose=False)
    clientList.append(client_ARQ_infinit_cwnd)
    serverList.append(server_ARQ_infinit_cwnd)

    client_UDP = EchoClient(clientId=401, serverId=411, 
        protocolName="UDP", transportParam={}, 
        trafficMode="periodic", trafficParam={"period":1, "pktsPerPeriod":1}, 
        verbose=False)
    server_UDP = EchoServer(serverId=411, ACKMode=None, verbose=False)
    clientList.append(client_UDP)
    serverList.append(server_UDP)






    ACKPacketList = []
    packetList_enCh = []
    packetList_deCh = []

    # clear each client server
    for c, s in zip(clientList, serverList):
        c.transportObj.instance.time = -1
        c.pid = 0
        c.time = -1
        s.time = -1
        

    channel._initBuffer()

    while not channel.isFull(): # fill the channel with environment packets
        packetList_enCh = bgclient.ticking(ACKPacketList)
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

        if time % recordingPeriod == 0:
            print("time ", time, " =================")
            print("RTT", client.transportObj.instance.SRTT)
            print("RTO", client.transportObj.instance.timeout)
            client, server = clientList[-1], serverList[-1]

            client.transportObj.instance.clientSidePerf()
            server.printPerf(
                client.getPktGen(),
                client.getProtocolName())
            
            deliveredPktEachServer = []
            for c, s in zip(clientList, serverList):
                deliveredPkts, deliveryRate, avgDelay = s.serverSidePerf(c.getPktGen())
                deliveredPktEachServer.append(deliveredPkts)

            throughputDetail.append(deliveredPktEachServer)

    throughputDesc = []
    for c, s in zip(clientList, serverList):
        desc = c.getProtocolName()+"[{}-{}]".format(c.uid, c.duid)
        throughputDesc.append(desc)

    return throughputDetail, throughputDesc
# test each pair of client and server

throughputVsProcessRateEachServer = []
for channelProcessRate in range(1, 10):
    throughputEachServer, throughputDesc = test_channel(channelProcessRate)
    throughputVsProcessRateEachServer.append(throughputEachServer)

print("throughput vs channel process rate")
print("   ")

data = {
    "throughputData":throughputVsProcessRateEachServer,
    "dataDesc": throughputDesc
    }

with open("throughput_data.pkl", 'wb') as handle:
    pkl.dump(data, handle, protocol=pkl.HIGHEST_PROTOCOL)
print("save to ", "throughput_data.pkl")