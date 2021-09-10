import pickle as pkl
import os, sys
import numpy as np


rstPath = sys.argv[1]
pklFileList = os.listdir(rstPath)

pklFileList = list(filter(lambda filename: filename[-3:] == "pkl", pklFileList))

betaFilenameDict = {}           # for overall MCP performance

for filename in pklFileList:
    beta1 = float(filename[:-4].split("_")[-2])
    beta2 = float(filename[:-4].split("_")[-1])

    with open(os.path.join(rstPath, filename), 'rb') as handle:
        data = pkl.load(handle)
        generalData = data["general"]
        header = data["header"]
        utilityParam = data["utilityParam"]

    for item in generalData:
        if item[0] == 'MCP':
            # betaFilenameDict[beta1] = [beta1, 1-beta1] + item[4:6] + item[8:10] + [data["MCP"]["clientPerf"]["retranProb"]]
            # retransProb = data["MCP"]["clientPerf"]["retransAttempts"] / (data["MCP"]["clientPerf"]["retransAttempts"] + data["MCP"]["clientPerf"]["ignorePkts"])
            retransProb = data["MCP"]["clientPerf"]["retranProb"]
            betaFilenameDict[beta1] = [beta1, 1-beta1] + item[4:11] + [retransProb]
            break

betaList = list(betaFilenameDict.keys())
betaList.sort()

cleanedRst = []
for key in betaList:
    cleanedRst.append(betaFilenameDict[key])

cleanedRst = np.asarray(cleanedRst)
np.set_printoptions(suppress=True)
print(cleanedRst.T)
np.savetxt(os.path.join(rstPath, "summary.csv"), cleanedRst.T, delimiter=",", fmt='%f')
