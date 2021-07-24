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

Follow the steps described in the `README.md` from that repository. Installing `geni-lib` and setting up user credentials
as described there are prerequisites for accessing CloudLab.

Update the config file with CloudLab-specific options inside: `cloudlab.config`. Options such as `site`, `hw_type`, and `node_count`
specify how many nodes and where should be allocated for each set of experiments run by this tool. The rest of the options in that file
relate to authentication and user credentials.

Then, you would want to run the `controller.py` script in the following way:

```
python controller.py --cloudlab --cloudlab_config cloudlab_allocator/cloudlab.config
```

If the code from `cloudlab_allocator` repo is imported properly, you should see a line
at the beginning of the produced log messages like this:

```
2021-07-23 13:44:14,076 __main__     DEBUG    Imported code for CloudLab integration.
```
