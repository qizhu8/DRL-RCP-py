import subprocess

# subprocess.call("test1.py", shell=True)

import numpy as np
# alphaList = [0, 0.25, 0.5, 1]
# beta1List = [10, 1, 0.1]
# beta2List = [10, 1, 0.1]

alphaList = [1]
beta1List = [10]
# beta2List = [20/np.log(100/3), 10/np.log(100/3), 5/np.log(100/3)]
# beta2List = [20/np.log(100/3), 10/np.log(100/3), 5/np.log(100/3), 2]
beta2List = [4]

for alpha in alphaList:
    for beta1 in beta1List:
        for beta2 in beta2List:
            alpha_str, beta1_str, beta2_str = str(alpha), str(beta1), str(beta2)
            pklFilename = "perfData2_{alpha}_{beta1}_{beta2}.pkl".format(alpha=alpha_str, beta1=beta1_str, beta2=beta2_str)
            subprocess.run(["python3 SimulationEnvironment2.py {} {} {} {}".format(alpha_str, beta1_str, beta2_str, pklFilename)], shell=True)
            subprocess.run(["python3 plotPerformance.py {}".format("results/"+pklFilename)], shell=True)

print("done")