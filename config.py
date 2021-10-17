# # SSH Configurations
# workers = ["hp065.utah.cloudlab.us"]
# user = "carina"
# keyfile = "/home/carina/.ssh/id_cloud"
# port_num = 22
#
# # Experiemnts Repo
# repo = "https://gitlab.flux.utah.edu/carina/os-benchmarks.git"
#
# # Filepaths and commands
# init_script_call = "cd os-benchmarks && bash initialize.sh"
# experiment_script_call = "cd os-benchmarks && python3 exp_config.py"
# results_dir = "~/os-benchmarks/results"
# results_file = "results.txt"
#
# # Options
# n_runs = 1
# verbose = True
# reboot = True
# seed = None

# SSH Configurations
#workers = ["ms0745.utah.cloudlab.us","ms0416.utah.cloudlab.us"]
workers = ["ms0745.utah.cloudlab.us"]
user = "carina"
keyfile = "/home/carina/.ssh/id_cloud"
port_num = 22

# Experiemnts Repo
repo = "https://gitlab.flux.utah.edu/carina/test-experiments.git"

# Filepaths and commands
init_script_call = "cd test-experiments && bash initialize.sh"
experiment_script_call = "cd test-experiments && python3 exp_config.py"
results_dir = "~/test-experiments/results"
results_file = "results.txt"

# Options
n_runs = 3
verbose = True
reboot = False
seed = None
