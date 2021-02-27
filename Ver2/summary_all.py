import pickle as pkl
import os
import numpy as np

rstPath = os.path.join("results")
pklFileList = os.listdir(rstPath)

pklFileList = list(filter(lambda filename: filename[-3:] == "pkl", pklFileList))

betaFilenameDict = {}

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
            betaFilenameDict[beta1] = [beta1, 1-beta1] + item[4:6] + [data["MCP"]["clientPerf"]["retranProb"]]
            break

betaList = list(betaFilenameDict.keys())
betaList.sort()

cleanedRst = []
for key in betaList:
    cleanedRst.append(betaFilenameDict[key])
cleanedRst = np.asarray(cleanedRst)
np.set_printoptions(suppress=True)
print(cleanedRst.T)
np.savetxt("summary.csv", cleanedRst.T, delimiter=",", fmt='%f')
