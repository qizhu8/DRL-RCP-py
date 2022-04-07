# How to run

Run the following python script under ```Ver2```

```
cd Ver2

# you can change the parameters in line experiment1.py line 5~10 to test more settings
python3 experiment1.py
# results are stored in ```summary.csv```


# generate the stability test result
# python3 TestMCPStability3.py [alpha] [beta1] [beta2]
python3 TestMCPStability3.py 2 0.1 0.9

# plot utility vs tick
# python3 plotPerformance.py <path to a pkl file> 
python3 plotPerformance.py results/alpha2/perfData2_2_0.0_1.0.pkl 
```