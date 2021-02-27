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


print("beta1:", utilityParam["beta1"])
print("beta2:", utilityParam["beta2"])

for protocol in data["protocols"]:
    print("======"+protocol+"=====")
    for key in data[protocol]["clientPerf"]:
        print("{key}:{val}".format(key=key, val=data[protocol]["clientPerf"][key]))

print(tabulate(generalData, headers=header))

with open(datafileName[:-4]+".txt", 'w') as f:
    f.write(tabulate(generalData, headers=header).__str__())



slidingWindow = 300

# plot utility information
f2 = plt.figure(2)
slidingWindow = 20
for protocolName in data["protocols"]:
    if protocolName in {"tcp_newreno"}:
        continue

    perfData = np.asarray(data[protocolName]["serverPerf"][2])

    # perfRecords = [timeIdx, deliveriedPkts, deliveryRate, avgDelay, avg_utility_per_pkt]
    dataToPlot = perfData[:, 4]
    xdata = perfData[:, 0]

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

    plt.plot(xdata[100:], dataToPlot[100:], label=protocolName)

plt.title("Utility over time (beta=[{},{}])".format(utilityParam["beta1"], utilityParam["beta2"]))
plt.yscale('symlog')
plt.xlabel("tick")
plt.ylabel("smoothed utility (per {window} ticks)".format(window=slidingWindow))
plt.legend()

plotname = "utility_vs_time_{}_{}".format(utilityParam["beta1"], utilityParam["beta2"])
plt.savefig("results/"+plotname + '.png')
# plt.show()

# MCP final performance (last 25% data)
