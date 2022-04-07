import subprocess
import os
import numpy as np

# alphaList = [1, 2, 4]
alphaList = [2]
# beta1List = [0.5]
# beta1List = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
# beta1List = [0, 0.3, 0.6, 1]
beta1List = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
simulationTime = 20000


# delete temp files
# subprocess.run(["rm -rf results/*"], shell=True)

# delete UDP/ARQ data history
subprocess.run(["rm *.pkl"], shell=True)

# subprocess.run(["rm TCP\ NewReno_perf.pkl"], shell=True)

for alpha in alphaList:
    alpha = np.round(alpha, 2)
    alpha_str = str(alpha)
    subprocess.run(["mkdir -p results/alpha{}".format(alpha)], shell=True)
    for beta1 in beta1List:
        beta1 = float(beta1)
        beta2 = 1 - beta1
        beta1_str, beta2_str = str(beta1), str(beta2)
        pklFilename = "perfData2_{alpha}_{beta1}_{beta2}.pkl".format(alpha=alpha_str, beta1=beta1_str, beta2=beta2_str)
        subprocess.run(["python3 SimulationEnvironment2.py {} {} {} {} {}".format(alpha_str, beta1_str, beta2_str, pklFilename, simulationTime)], shell=True)

        pklFilePath = os.path.join("results", "alpha{alpha}".format(alpha=alpha), pklFilename)
        # subprocess.run(["python3 plotPerformance.py {}".format(pklFilePath)], shell=True)

    subprocess.run(["python3 summary_all.py {}".format(os.path.join("results", "alpha{alpha}".format(alpha=alpha)))], shell=True)

print("done")
# subprocess.run(["sudo shutdown -h now"], shell=True)
