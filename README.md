# Sigmetrics Tool

This repo contains the code for running benchmarks in fixed/randomized orders on specified remote resources.

## To Start

If you don't have `conda` on the machine where you are running this code, do the following (it will install `miniconda`; doesn't requre root priviledges):

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

Now, you are ready to run the controller script. Basic usage:

```
python controller.py
```

## Using CloudLab resources

In order to use the code for allocating CloudLab nodes, which is available at:
[https://gitlab.flux.utah.edu/emulab/cloudlab_allocator`](https://gitlab.flux.utah.edu/emulab/cloudlab_allocator),
clone that repo *inside* the directory with the files from this repo:
```
git clone https://gitlab.flux.utah.edu/emulab/cloudlab_allocator.git
```  

Follow the steps described in the `README.md` from that repository. Installing `geni-lib` and setting up user credentials as described there are prerequisites for accessing CloudLab.

Update the config file with CloudLab-specific options inside: `cloudlab.config`. Options such as `site`, `hw_type`, and `node_count` specify how many nodes and where should be allocated for each set of experiments run by this tool. The rest of the options in that file
relate to authentication and user credentials.

Then, you would want to run the `controller.py` script in the following way:

```
python controller.py --cloudlab --cloudlab_config cloudlab_allocator/cloudlab.config
```

If the code from `cloudlab_allocator` repo is imported properly, you should see a line at the beginning of the produced log messages like this:

```
2021-07-23 13:44:14,076 __main__     DEBUG    Imported code for CloudLab integration.
```

## Using Controller Script

### Config.py

Users must fill out `config.py` prior to usage of the controller script. Configuration must include the SSH information for the worker node (unless Cloudlab resources will be used), the repository that will contain the experiments, the paths to the specified files and directories, and optional debugging and random seed information.

### Experiment Repository Requirements

#### Initialization

Experiment repositories should contain a script `initialization.sh` that sets up the worker node(s) to ready them for experimentation. Our controller script will run the script before experimentation and reboot to achieve a clean state.

#### Experiment Configuration File

The controller script requires the set of experiments to be run in the form of their command line command and arguments. For example:

```
bash exp_1.sh -r 20
```

All experiment commands must be included in a single-column file, and the file path must be entered as `configfile_path` in the controllers configuration file. It is from this file that the controller will distinguish an arbitrary fixed order from randomized orders.

### During experimentation

Experiments will be executed in a fixed, arbitrary order (known as a run). A run will be repeated a number of times specified by the user in `config.py`. The remote worker(s) will be rebooted after each run to ensure a clean machine state. The experiments will then be randomized using a user-provided seed or epoch time seed as a default and run. Re-randomization and execution of the experiments will occur a number of times specified by the user in `config.py`. Worker node(s) will be rebooted for a clean state between each run.

 **Debugging:** All debug information will be saved to a log file. In `config.py`, a verbose=True will direct STDOUT to be printed to the terminal as DEBUG information. Any errors during execution and information statements will be both saved to the log file and printed to the terminal.

### Results

Results will be saved to a timestamped folder in the `sigmetrics-tool` repository. A single results folder contains metadata of each run (found in `run_results.csv`) in addition the results of each experiment (in `exp_results.csv`), and the machine specs of the worker node(s) (in `env_out.csv`). Experiment results will include the returned result of the experiment, as well as a report of success or failure.

#### Result Requirments

In order to automate the collection of results and statistical analysis of experiment order, the user must meet some requirements when gathering results:

1. Results from each experiment must collected and stored in a text file (file name specified in `config.py` as `results_file`) as a single column of floating-point numbers written in the order the experiments were called by the controller script.
2. Result text file and machine spec information will moved to a results directory and transferred to the controller node together. The results directory path must be specified by the user in `config.py` as `results_dir`.
3. All failed experiments must return a non-zero exit code, and also a value of the user's choice in the results text file.
