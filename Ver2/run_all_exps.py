import subprocess

import numpy as np

alphaList = [1]
# beta1List = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
# beta1List = [0, 0.3, 0.6, 1]
# beta1List = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
beta1List = [1]
# beta2List = [0.5]
simulationTime = 20000

# delete temp files
subprocess.run(["rm results/*"], shell=True)

# delete UDP/ARQ data history
# subprocess.run(["rm *.pkl"], shell=True)


for beta1 in beta1List:
    beta2 = 1 - beta1
    beta1_str, beta2_str = str(beta1), str(beta2)
    pklFilename = "perfData2_{beta1}_{beta2}.pkl".format(beta1=beta1_str, beta2=beta2_str)
    subprocess.run(["python3 SimulationEnvironment2.py {} {} {} {}".format(beta1_str, beta2_str, pklFilename, simulationTime)], shell=True)
    subprocess.run(["python3 plotPerformance.py {}".format("results/"+pklFilename)], shell=True)



print("done")
# subprocess.run(["sudo shutdown -h now"], shell=True)
