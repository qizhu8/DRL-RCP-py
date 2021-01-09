1. applications.py contains SimpleServer and SimpleClient implementation.
2. channel.py implements the simulated channel model that uses channelBuffer (DropTailQueue with more details).
3. packet.py contains two important data structures, Packet and PacketInfo. Packet simulates packets to be transmitted in the network, and PacketInfo is the structure stored at the client side (Tx buffer) to record the packet information (flying time, queuing delay, transmission attempts, etc.)
4. RL_Brain.py implements a general DQN and the related neural network. 
5. test_RL_brain.py makes use of the `CartPole` experiment in `gym` library to test the functionality of RL_Brain.
6. MCP_client.py is our customized client.
7. SimulationEnvironment.py sets up the simulation environment.

Requirements for the network simulation:
torch, numpy

Additional requirements for the gym experiment:
pyglet - Windowing and graphics
pyopengl - rendering