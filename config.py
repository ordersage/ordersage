"""
SSH Configurations
"""
# pre-allocated worker nodes must be added here by hostname
workers = ["hostname"]
user = "user"
keyfile = "~/.ssh/id_ed25519"
port_num = 22

"""
Experiemnt Repo
"""
repo = "https://gitlab.flux.utah.edu/carina/test-experiments.git"

"""
Filepaths and commands on worker node
"""
init_script_call = "cd test-experiments && bash initialize.sh"
exp_script_call = "cd test-experiments && python3 exp_config.py"
results_dir = "~/test-experiments/results"
results_file = "results.txt"

"""
Controller options
"""
# specifies the number of runs for both fixed and random order
n_runs = 3
# specifies if random and fixed runs should be interleaved or not
interleave = True
# prints STDOUT of workers to console
verbose = True
# Ignore reset command for debugging purposes
reset = False
# Set your own random seed
seed = None
