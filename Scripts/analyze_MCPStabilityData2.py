import pickle as pkl
import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt


parser = argparse.ArgumentParser(description='Analyze MCP Stability 2 Data')
parser.add_argument("-p", "--path", type=str,
                    help="pkl file to be analyzed")
args = parser.parse_args()

# get the ip and port of the server
pklFilename = args.path


with open(pklFilename, 'rb') as handle:
    data = pkl.load(handle)

processRate = data["processRate"]

for idx, ch_bandwidth in enumerate(processRate):
    f = plt.figure(idx)
    throughput_data_per_trial = np.asarray(data["throughputData"][idx])
    rounds, streams = throughput_data_per_trial.shape
    for streamId in range(streams):
        plt.plot(throughput_data_per_trial[:, streamId], label=data["dataDesc"][streamId])
    plt.title("ch bandwidth "+str(ch_bandwidth))
    f.legend()
    f.show()
plt.show()

# for ch_bandwidth in range(1, 10):
#     data


