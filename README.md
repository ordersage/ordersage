# Sigmetrics Tool

This repo contains the code for running benchmarks in fixed/randomized orders on specified remote resources.

## To Start

If you don't have `conda` on the machine where you are running this code, do the following (it will install `miniconda`; doesn't requre root priviledges):

```
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh -O ~/miniconda.sh
bash ~/miniconda.sh -b -p $HOME/miniconda
```

After this, you might need to run: `~/miniconda/bin/conda init` (unless the installation procedure prompts about initializaton already). Then, you might need to close current terminal window and open a new one--this will make the `conda` command available.

When you have `conda` installed and initialized, create a new environment using the file provided in this repo:

```
conda create -f environment.yml
```

To initialize the environment, do: `conda activate sigmetrics-tool`

Now, you are ready to run the controller script. Basic usage:

```
python controller.py
```
