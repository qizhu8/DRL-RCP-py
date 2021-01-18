import matplotlib.pyplot as plt
import pickle as pkl
import numpy as np

with open('perfData2.pkl', 'rb') as handle:
    data = pkl.load(handle)

generalData = data["general"]
header = data["header"]

slidingWindow = 30

# plot delivery information
f1 = plt.figure(1)
for protocolName in data:
    if protocolName in {"general", "header"}:
        continue
    
    pktsPerTick = np.asarray(data[protocolName][0])

    # method 1: convolution
    # smoothedData = np.convolve(pktsPerTick, np.ones((slidingWindow, )))
    # method 2: count per $slidingWindow tick
    smoothedData = np.concatenate((pktsPerTick, np.zeros(slidingWindow - len(pktsPerTick) % slidingWindow)))
    smoothedData = np.reshape(smoothedData, [slidingWindow, len(smoothedData)//slidingWindow])
    smoothedData = np.sum(smoothedData, axis=0)

    xdata = np.arange(len(smoothedData))*slidingWindow
    plt.plot(xdata, smoothedData, label=protocolName)

plt.title("delivered packets over time")
plt.xlabel("tick")
plt.ylabel("smoothed rate (per {window} ticks)".format(window=slidingWindow))
plt.legend()





# plot utility information
f2 = plt.figure(2)
slidingWindow = 30
for protocolName in data:
    if protocolName in {"general", "header"}:
        continue

    perfRecords = np.asarray(data[protocolName][1])

    # perfRecords = [deliveriedPkts, deliveryRate, avgDelay, avg_utility_per_pkt, utility_sum]
    print(perfRecords.shape)
    utilityInATick = perfRecords[:, -1]

    # method 1: convolution
    smoothedData = np.convolve(utilityInATick, np.ones((slidingWindow, )))
    plt.plot(smoothedData, label=protocolName)

    # method 2: count per $slidingWindow tick
    # smoothedData = np.concatenate((utilityInATick, np.zeros(slidingWindow - len(pktsPerTick) % slidingWindow)))
    # smoothedData = np.reshape(smoothedData, [slidingWindow, len(smoothedData)//slidingWindow])
    # smoothedData = np.sum(smoothedData, axis=0)
    # xdata = np.arange(len(smoothedData))*slidingWindow
    # plt.plot(xdata, smoothedData, label=protocolName)

plt.title("Utility over time")
plt.xlabel("tick")
plt.ylabel("smoothed utility (per {window} ticks)".format(window=slidingWindow))
plt.legend()

plt.show()

