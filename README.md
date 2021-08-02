# Sigmetrics Tool

This repo contains the code for running benchmarks in fixed/randomized orders on specified remote resources.

## To Start

#### 1. Update `config.py`

Users must fill out or update `config.py` prior to usage of the controller script. Configuration must include the SSH information for the worker node (unless Cloudlab resources will be used), the repository that will contain the experiments, the paths to the specified files and directories, and optional debugging and random seed information.

Additionally, `config.py` must contain commands to run an initialization script (see `Initialization`) and a script that prints all experiments commands that will be used to stdout.

#### 2. Get all dependencies (set up environment)

Users must have a working Python environment with such packages as `paramiko`, `pandas`, and `numpy`, among others imported at the top of `controller.py` script. The easiest way to set up such environment is with the `conda` environment manager (instructions below show how `miniconda` can be installed, which is the minimal version of that).

If you don't have `conda` on the machine where you are running this code, do the following (it will install `miniconda`; it doesn't require root priviledges):

```
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh -O ~/miniconda.sh
bash ~/miniconda.sh -b -p $HOME/miniconda
```

After this, you might need to run: `~/miniconda/bin/conda init` (unless the installation procedure prompts about initialization already). Then, you might need to close current terminal window and open a new one--this will make the `conda` command available.

When you have `conda` installed and initialized, create a new environment using the file provided in this repo:

```
conda create -f environment.yml
```

To initialize the environment, do: `conda activate sigmetrics-tool`

Always make sure that you run this `activate` command *before* running `controller.py`.

#### 3. Set up experiment repository

Inside `config.py`, update `repo` option to make it point at the specific public repo with experiments that need to be run.

Examples of such repo can be seen at: [https://gitlab.flux.utah.edu/carina/test-experiments](https://gitlab.flux.utah.edu/carina/test-experiments)
and [https://gitlab.flux.utah.edu/Duplyakin/test-experiments](https://gitlab.flux.utah.edu/Duplyakin/test-experiments)

##### Initialization

Experiment repositories should contain a script `initialization.sh` that sets up the worker node(s) to ready them for experimentation. Our controller script will run the script before experimentation and reboot to achieve a clean state. Initialization must include the creation of a results directory whose location is recorded in `config.py`.

##### Experiment Configuration File

The controller script requires the set of experiments to be run in the form of their command line command and arguments. For example:

```
bash exp_1.sh -r 20
```

All experiment commands must be printed on new lines to stdout by running a script on a remote machine. The controller node will execute the remote script by running the command specified in `config.py` over an established ssh connection. It is from this script that the controller will distinguish an arbitrary fixed order from randomized orders.

#### 4. Optional: Get code for allocating CloudLab nodes

In order to use the code for allocating CloudLab nodes, which is available at:
[https://gitlab.flux.utah.edu/emulab/cloudlab_allocator](https://gitlab.flux.utah.edu/emulab/cloudlab_allocator),
clone that repo *inside* the directory with the files from this repo:
```
git clone https://gitlab.flux.utah.edu/emulab/cloudlab_allocator.git
```  

Follow the steps described in the `README.md` from that repository.
Installing `geni-lib` and setting up user credentials as described there are prerequisites for accessing CloudLab.

Update the config file with CloudLab-specific options inside: `cloudlab.config`.
Options such as `site`, `hw_type`, and `node_count` specify how many nodes and where should be allocated for each set of experiments run by this tool.
The rest of the options in that file relate to authentication and user credentials.

If you decide to skip this step (and use a preallocated node, on CloudLab or elsewhere),
make sure to update `config.py`, as described in step 1 above, and, specifically,
set the `worker` option to the hostname of that preallocated node.

## To Run

#### Basic Usage (with preallocated node)

After following steps above, run:

```
python controller.py
```

#### Running with allocation of CloudLab nodes

In this mode, you would want to run the `controller.py` script in the following way:

```
python controller.py --cloudlab --cloudlab_config cloudlab_allocator/cloudlab.config
```

If the code from `cloudlab_allocator` repo is imported properly,
you should see a line at the beginning of the produced log messages like this:

```
2021-07-23 13:44:14,076 __main__     DEBUG    Imported code for CloudLab integration.
```

## During experimentation

Experiments will be executed in a fixed, arbitrary order (known as a run). A run will be repeated a number of times specified by the user in `config.py`. The remote worker(s) will be rebooted after each run to ensure a clean machine state. The experiments will then be randomized using a user-provided seed or epoch time seed as a default and run. Re-randomization and execution of the experiments will occur a number of times specified by the user in `config.py`. Worker node(s) will be rebooted for a clean state between each run.

**Debugging:** All debug information will be saved to a log file. In `config.py`, `verbose=True` will direct STDOUT to be printed to the terminal as DEBUG information. Any errors during execution and information statements will be both saved to the log file and printed to the terminal.

## Results

Results will be saved to a timestamped folder in the `sigmetrics-tool` repository. A single results folder contains metadata of each run (found in `run_results.csv`) in addition the results of each experiment (in `exp_results.csv`), and the machine specs of the worker node(s) (in `env_out.csv`). Experiment results will include the returned result of the experiment, as well as a report of success or failure.

##### Result Requirements

In order to automate the collection of results and statistical analysis of experiment order, the user must meet some requirements when gathering results in the code implemented as part of the experiment repository:

1. Results from each experiment must be collected and stored in a text file (file name specified in `config.py` as `results_file`) as a single column of floating-point numbers written in the order the experiments were called by the controller script.
2. Result text file and machine spec information will moved to a results directory and transferred to the controller node together. The results directory path must be specified by the user in `config.py` as `results_dir`.
3. All failed experiments must return a non-zero exit code, and also a value of the user's choice in the results text file.
