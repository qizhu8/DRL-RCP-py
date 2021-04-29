import pickle as pkl
import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt


def calcUtility(deliveryRate, avgDelay, alpha, beta1, beta2, UDP_delivery, ARQ_delivery, UDP_delay, ARQ_delay):
    # def sigmoid(x):
    #     return 1/ (1 + np.exp(-x))
    # r = beta1*deliveryRate + beta2/np.log(avgDelay+2)
    # r = beta1 * deliveryRate + beta2 * ( -2 * sigmoid(avgDelay / 100) + 2 )
    # linear utility

    UDP_dlvy, UDP_dly = UDP_delivery*0.9, UDP_delay*0.9
    ARQ_dlvy, ARQ_dly = ARQ_delivery*1.1, ARQ_delay*1.1

    
    dlvy = (deliveryRate - UDP_dlvy) / (ARQ_dlvy - UDP_dlvy)
    q = (avgDelay - UDP_dly) / (ARQ_dly-UDP_dly)

    # dlvy = deliveryRate
    # q = avgDelay / 611.003

    # r = beta1*normalized_dlvy + beta2 * (1 - normalized_dly) # (0.6, 101) & (1.0, 672)

    r = -beta1*((1-dlvy)**alpha) - beta2*(q**alpha)

    return r

parser = argparse.ArgumentParser(description='Analyze MCP Stability 3 Data')
parser.add_argument("-p", "--path", type=str, required=True,
                    help="pkl file to be analyzed")

args = parser.parse_args()

# get the ip and port of the server
pklFilename = args.path


with open(pklFilename, 'rb') as handle:
    data = pkl.load(handle)

utilParam = data["utilParam"]
chParamInst = data["chParamInst"]
dataDesc = data["dataDesc"]
throughputData = data["throughputData"]
MCPPerf = data["MCPPerf"]
delayData = data["delayData"]
deliveryRateData = data["deliveryRateData"]

alpha, beta1, beta2 = utilParam

UDP_streamid = -1
ARQ_streamid = -1
MCP_streamid = -1

for idx, desc in enumerate(dataDesc):
    if desc.startswith("UDP"):
        UDP_streamid = idx
    if desc.startswith("ARQ"):
        ARQ_streamid = idx
    if desc.startswith("MCP"):
        MCP_streamid = idx

for idx in range(len(throughputData)):

    UDP_delivery, ARQ_delivery = deliveryRateData[idx][-1][UDP_streamid], deliveryRateData[idx][-1][ARQ_streamid]
    UDP_delay, ARQ_delay = delayData[idx][-1][UDP_streamid], delayData[idx][-1][ARQ_streamid]

    print(UDP_delivery, ARQ_delivery)
    print(UDP_delay, ARQ_delay)

    # plot throughput
    f = plt.figure(idx*4+0)
    throughput_data_per_trial = np.asarray(throughputData[idx])

    throughput_data_per_trial[1:-1, :] -= throughput_data_per_trial[0:-2, :] 
    throughput_data_per_trial = throughput_data_per_trial[:-1, :]  # remove the last item

    timeline = np.asarray(range(len(throughput_data_per_trial[:, 0]))) * 30

    rounds, streams = throughput_data_per_trial.shape
    for streamId in range(streams):
        plt.plot(timeline, throughput_data_per_trial[:, streamId], label=dataDesc[streamId])
    f.legend()
    f.show()

    # plot MCP retrans prob
    f = plt.figure(idx*4+1)
    MCPretransAttempts = np.asarray(MCPPerf["retransAttempts"])

    MCPretransAttempts[1:-1] -= MCPretransAttempts[0:-2] 
    MCPretransAttempts = MCPretransAttempts[:-1]  # remove the last item

    timeline = np.asarray(range(len(MCPretransAttempts))) * 30

    plt.plot(timeline, MCPretransAttempts, label="MCP Retrans Attempts")
    f.legend()
    f.show()

    # plot MCP retrans attempts
    f = plt.figure(idx*4+2)
    MCPretranProb = np.asarray(MCPPerf["retranProb"])

    timeline = np.asarray(range(len(MCPretranProb))) * 30

    plt.plot(timeline, MCPretranProb, label="MCP Retrans Prob")
    f.legend()
    f.show()

    # plot UDP, MCP, ARQ utility vs time
    f = plt.figure(idx*4+3)
    UDP_utilList, MCP_utilList, ARQ_utilList = [], [], []
    for slotId in range(len(deliveryRateData[idx])):
        UDP_util = calcUtility(
            deliveryRate=deliveryRateData[idx][slotId][UDP_streamid], 
            avgDelay=delayData[idx][slotId][UDP_streamid], 
            alpha=alpha, beta1=beta1, beta2=beta2, UDP_delivery=UDP_delivery, ARQ_delivery=ARQ_delivery, 
            UDP_delay=UDP_delay, ARQ_delay=ARQ_delay)
        UDP_utilList.append(UDP_util)

        MCP_util = calcUtility(
            deliveryRate=deliveryRateData[idx][slotId][MCP_streamid], 
            avgDelay=delayData[idx][slotId][MCP_streamid], 
            alpha=alpha, beta1=beta1, beta2=beta2, UDP_delivery=UDP_delivery, ARQ_delivery=ARQ_delivery, 
            UDP_delay=UDP_delay, ARQ_delay=ARQ_delay)
        MCP_utilList.append(MCP_util)

        ARQ_util = calcUtility(
            deliveryRate=deliveryRateData[idx][slotId][ARQ_streamid], 
            avgDelay=delayData[idx][slotId][ARQ_streamid], 
            alpha=alpha, beta1=beta1, beta2=beta2, UDP_delivery=UDP_delivery, ARQ_delivery=ARQ_delivery, 
            UDP_delay=UDP_delay, ARQ_delay=ARQ_delay)
        ARQ_utilList.append(ARQ_util)
    
    plt.plot(timeline, UDP_utilList, label=dataDesc[UDP_streamid])
    plt.plot(timeline, MCP_utilList, label=dataDesc[MCP_streamid])
    plt.plot(timeline, ARQ_utilList, label=dataDesc[ARQ_streamid])

    slotId = 5000//30+1
    print("at time 5000")
    print("UDP:", 1-deliveryRateData[idx][slotId][UDP_streamid], delayData[idx][slotId][UDP_streamid], UDP_utilList[slotId])
    print("ARQ:", 1-deliveryRateData[idx][slotId][ARQ_streamid], delayData[idx][slotId][ARQ_streamid], ARQ_utilList[slotId])
    print("MCP:", 1-deliveryRateData[idx][slotId][MCP_streamid], delayData[idx][slotId][MCP_streamid], MCP_utilList[slotId])
    slotId = len(deliveryRateData[idx])-1
    print("at last")
    print("UDP:", 1-deliveryRateData[idx][slotId][UDP_streamid], delayData[idx][slotId][UDP_streamid], UDP_utilList[slotId])
    print("ARQ:", 1-deliveryRateData[idx][slotId][ARQ_streamid], delayData[idx][slotId][ARQ_streamid], ARQ_utilList[slotId])
    print("MCP:", 1-deliveryRateData[idx][slotId][MCP_streamid], delayData[idx][slotId][MCP_streamid], MCP_utilList[slotId])

    f.legend()
    f.show()

plt.show()


import csv
import numpy as np

with open('throughput_data.csv', mode='w') as fp:
    writer = csv.writer(fp, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(dataDesc)
    for streamId in range(5):
        writer.writerow(throughput_data_per_trial[:, streamId])
    writer.writerow(MCPretransAttempts)

