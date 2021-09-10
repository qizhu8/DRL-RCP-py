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