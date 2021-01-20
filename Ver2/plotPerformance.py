import matplotlib.pyplot as plt
import pickle as pkl
import numpy as np
import sys
from tabulate import tabulate


if len(sys.argv) > 1:
    if isinstance(sys.argv[1], str) and sys.argv[1].endswith(".pkl"):
        datafileName = sys.argv[1]
else:
    datafileName = 'perfData2.pkl'

with open(datafileName, 'rb') as handle:
    data = pkl.load(handle)

generalData = data["general"]
header = data["header"]
utilityParam = data["utilityParam"]


print("alpha:", utilityParam["alpha"])
print("beta1:", utilityParam["beta1"])
print("beta2:", utilityParam["beta2"])


print(tabulate(generalData, headers=header))

with open("txt"+datafileName[:-4]+".txt", 'w') as f:
    f.write(tabulate(generalData, headers=header).__str__())



slidingWindow = 300

# plot delivery information
# f1 = plt.figure(1)
# for protocolName in data:
#     if protocolName in {"general", "header", "utilityParam"}:
#         continue
    
#     dataToPlot = np.asarray(data[protocolName][0])

#     """method 1: convolution"""
#     # dataToPlot = np.convolve(dataToPlot, np.ones((slidingWindow, )))
#     # dataToPlot = dataToPlot[:-slidingWindow+1]
#     # xdata = np.arange(len(dataToPlot))
#     """method 2: count per $slidingWindow tick"""
#     # dataToPlot = np.concatenate((dataToPlot, np.zeros(slidingWindow - len(dataToPlot) % slidingWindow)))
#     # dataToPlot = np.reshape(dataToPlot, [slidingWindow, len(dataToPlot)//slidingWindow])
#     # dataToPlot = np.sum(dataToPlot, axis=0)
#     # xdata = np.arange(len(dataToPlot))*slidingWindow

#     """method 3: direct print"""
#     xdata = np.arange(len(dataToPlot))

#     plt.plot(xdata, dataToPlot, label=protocolName)


# plt.title("delivered packets over time")
# plt.xlabel("tick")
# plt.ylabel("smoothed rate (per {window} ticks)".format(window=slidingWindow))
# plt.legend()





# plot utility information
f2 = plt.figure(2)
slidingWindow = 20
for protocolName in data:
    if protocolName in {"general", "header", "utilityParam"} | {"tcp_newreno"}:
        continue

    perfData = np.asarray(data[protocolName][1])

    # perfRecords = [deliveriedPkts, deliveryRate, avgDelay, avg_utility_per_pkt, utility_sum]
    dataToPlot = perfData[:, 4]
    xdata = perfData[:, 0]

    print(protocolName, "avg:", np.mean(dataToPlot))

    """method 1: convolution"""
    dataToPlot = np.convolve(dataToPlot, np.ones((slidingWindow, )))
    dataToPlot = dataToPlot[:-slidingWindow+1]
    """method 2: count per $slidingWindow tick"""
    # dataToPlot = np.concatenate((dataToPlot, np.zeros(slidingWindow - len(dataToPlot) % slidingWindow)))
    # dataToPlot = np.reshape(dataToPlot, [slidingWindow, len(dataToPlot)//slidingWindow])
    # dataToPlot = np.sum(dataToPlot, axis=0)
    # xdata = np.concatenate((xdata, np.zeros(slidingWindow - len(xdata) % slidingWindow)))
    # xdata = np.reshape(xdata, [slidingWindow, len(xdata)//slidingWindow])
    # xdata = xdata[0, :]

    """method 3: directly print"""

    plt.plot(xdata[10:], dataToPlot[10:], label=protocolName)

plt.title("Utility over time (alpha={} beta=[{},{}])".format(utilityParam["alpha"], utilityParam["beta1"], utilityParam["beta2"]))
plt.yscale('symlog')
plt.xlabel("tick")
plt.ylabel("smoothed utility (per {window} ticks)".format(window=slidingWindow))
plt.legend()

plotname = "utility_vs_time_{}_{}_{}".format(utilityParam["alpha"], utilityParam["beta1"], utilityParam["beta2"])
plt.savefig("results/"+plotname + '.png')
# plt.show()

