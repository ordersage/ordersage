"""
SSH Configurations
"""
# pre-allocated worker nodes must be added here by hostname
workers = ["ms0745.utah.cloudlab.us"]
user = "carina"
keyfile = "/home/carina/.ssh/id_cloud"
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
n_runs = 3
interleave = True
verbose = True
reset = False
seed = None
