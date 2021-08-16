# SSH Configurations
workers = ["ms0745.utah.cloudlab.us", "ms0314.utah.cloudlab.us"]
user = "carina"
keyfile = "/home/carina/.ssh/id_cloud"
port_num = 22

# Experiemnts Repo
repo = "https://gitlab.flux.utah.edu/carina/test-experiments.git"

# Filepaths and commands
init_script_call = "cd test-experiments && ./initialize.sh"
experiment_script_call = "bash ~/test-experiments/exp_config.sh"
results_dir = "~/test-experiments/results"
results_file = "results.txt"

# Options
verbose = True
reboot = False
seed = None
