from Applications import SimpleServer, SimpleClient
from channel import SingleModeChannel
from MCP_Client import MCP_Client
from MCP_Server import MCP_Server

"""
    Initialize Environments

    Note that user id, including clientId and serverId, should be distinct.
"""

#client 1 sends to server 1
# client1 = SimpleClient(clientId=1, serverId=2, timeout=3, appMode="window arq", param={"cwnd":2, "ACKMode":"LC"}, verbose=False)
# server1 = SimpleServer(serverId=2, ACKMode="LC", verbose=False)
client1 = SimpleClient(clientId=1, serverId=4, appMode="periodic", param={"period":3, "pktsPerPeriod": 0, "offset": 5, "ACKMode": None}, verbose=False)
server1 = SimpleServer(serverId=2, ACKMode=None , verbose=False)


# client 2 sends to server 2
client2 = SimpleClient(clientId=3, serverId=4, appMode="periodic", param={"period":3, "pktsPerPeriod": 3, "offset": 5, "ACKMode": None}, verbose=False)
server2 = SimpleServer(serverId=4, ACKMode=None , verbose=False)

client3 = SimpleClient(clientId=5, serverId=6, appMode="periodic", param={"period":10, "pktsPerPeriod": 100, "offset": 3, "ACKMode": None}, verbose=False)
server3 = SimpleServer(serverId=6, ACKMode=None , verbose=False)

client_RL = MCP_Client(clientId=100, serverId=101, timeout = 3, param={"period":3, "pktsPerPeriod": 4, "offset": 3, "ACKMode": None}, verbose=False)
server_RL = MCP_Server(serverId=101, verbose=False)


clientSet = {client1, client2, client3, client_RL}
serverSet = {server1, server2, server3, server_RL}
channel = SingleModeChannel(processRate=3, bufferSize=100, pktDropProb=0, verbose=False)

# system time
simulationPeriod = int(10000) # unit ticks / time slots
ACKPacketList = []
packetList_enCh = []
packetList_deCh = []

for time in range(1, simulationPeriod):
    # print("time ", time)
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
    if time % 500 == 0:
        print("===="*20)
        print("time: ",time)
        server_RL.printPerf()
        client_RL.printPerf()

print("===="*20)
print("time: ",time)
server_RL.printPerf(client_RL.pid-1)
client_RL.printPerf()
