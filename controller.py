# system libraries
import sys
import subprocess
import argparse

# Time libraries and RNG
from time import sleep
from datetime import datetime
import random

# SSH libraries
import paramiko
from scp import SCPClient

# error handling and logging
from requests import ConnectionError
import logging

# Subprocess functions
from subprocess import Popen, PIPE, STDOUT, run

# dataframe libraries
import pandas as pd
import numpy as np

# uuid library
import uuid

# Configuration file
import config

class RemoteClient():
    def __init__(self, server, portnum, uname, keyfile):
        self.server = server
        self.portnum = portnum
        self.uname = uname
        self.keypath = keyfile

def configure_logging(debug=False, filename='mylog.log'):
    """ This function configures logging facility.
    The current setup is for printing log messages onto console AND onto the file.
    Formatters are the same for both output destinations.
    Handing of log levels:
    - console output includes DEBUG messages or not depending on the `debug` argument.
    - file ouput includes all levels including DEBUG.
    """
    frmt_str = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
    frmt_out = '%(message)s'

    # set up logging to file
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(filename)
    f_formatter = logging.Formatter(frmt_str)
    file_handler.setFormatter(f_formatter)
    logger.addHandler(file_handler)

    # define a handler for console
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if debug else logging.INFO)
    formatter = logging.Formatter(frmt_out)
    console.setFormatter(formatter)
    logger.addHandler(console)

    return logger

LOG = configure_logging(debug=True)

def parse_args():
    pass

def open_ssh_connection(sshC, timeout=10, max_tries=3):
    """ Attempts to establish and SSH connection to worker node specified in config.
    If successful, this function will return an SSH client with open connection to
    the worker.
    """
    n_tries = 0
    ssh = paramiko.SSHClient()
    # what if it is an rsa key?
    sshkey = paramiko.Ed25519Key.from_private_key_file(sshC.keypath)
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # SSH Connect
    while True:
        try:
            ssh.connect(hostname = sshC.server, port = sshC.portnum, username = sshC.uname, pkey = sshkey, timeout = timeout)
        except Exception as e:
            n_tries += 1
            LOG.error("In open_ssh_connection: " + repr(e) + " - " + str(e))
            LOG.error("Error #" + str(n_tries) + " out of " + str(max_tries) + ".")
            if n_tries >= max_tries:
                LOG.error("Failure to connect to " + sshC.server, exc_info=True)
                raise ConnectionError("Failure to connect to " + sshC.server + "...exiting.")
            else:
                print("\tRetrying...")
        else:
            LOG.info("SSH connection to " + sshC.server + " successful.")
            return ssh

#TODO: Add in retry option...same for local or remote failure?
def execute_remote_command(ssh_client, cmd, verbose=False, max_tries=1):
    n_tries = 0
    while True:
        try:
            channel = ssh_client.get_transport().open_session()
            channel.set_combine_stderr(True)
            channel.exec_command(cmd)
            # Print output as it is received
            #TODO: add tab to each line of output
            while True:
                output = channel.recv(1024)
                if not output:
                    break
                else:
                    # Sometimes this could be an error not info, look into how to check
                    out = output.decode('utf-8').splitlines()
                    for o in out:
                        LOG.info("\t" + o)
        # Command failed locally
        except Exception as e:
            LOG.error("\tSSH exception while executing " + cmd)
            return "Failure"
        else:
            # Command failed remotely
            exit_status = channel.recv_exit_status()
            if exit_status != 0:
                LOG.error("\tError executing command: " + cmd)
                LOG.error("\tExit status: " + str(exit_status))
                return "Failure"
            channel.close()
            return "Success"

#TODO: Add print option for stderr
def execute_local_command(ssh, cmd, function_name="execute_local_command", verbose=False, max_tries=1):
    n_tries = 0
    while True:
        try:
            out = subprocess.run(cmd, stderr=STDOUT, stdout=PIPE)
        except Exception as ex:
            LOG.error("Error executing " + " ".join(cmd) + ": " + repr(ex))
        else:
            if out.returncode == 0:
                # Only prints blank line
                LOG.info(out.stdout.decode('utf-8'))
                break
            else:
                n_tries += 1
                if n_tries > max_tries:
                    return "Failure"
                else:
                    LOG.error("\tError in "+ function_name + " retrying (" + str(n_tries) + " out of " + str(max_tries) + ")...")
                    LOG.error(out.stdout.decode('utf-8'))

    return "Success"

def reboot(ssh_client, server):
    LOG.info("Rebooting...")
    execute_remote_command(ssh_client,"sudo reboot")

    # Spin until the machine comes up and is ready for SSH
    # Still printing to stdout...
    n_tries = 0
    max_tries = 8
    LOG.info("Awaiting completion of reboot for " + server + ", sleeping for 2 minutes...")
    sleep(120)
    while True:
        try:
            # Look into alternative here
            out = run(["nc", "-z", "-v", "-w5", server, "22"],stderr=STDOUT, stdout=PIPE)
        except:
            print("In reboot: " + repr(e) + " - " + str(e))
        else:
            if out.returncode == 0:
                break
            else:
                n_tries += 1
                if n_tries > max_tries:
                    return "Failure"
                else:
                    LOG.error("\tConnection attempt to " + server + " timed out, retrying (" + str(n_tries) + " out of " + str(max_tries) + ")...")
                    sleep(60)

    print("Node " + server + " is up at " + str(datetime.today()))
    return "Success"

#
# Initialize Remote Server
#
def initialize_remote_server(sshC, repo, config_path, dest_dir):
    ssh = open_ssh_connection(sshC)
    max_tries = 3
    n_tries = 0

    # set up results directory and clone repo
    LOG.info("Cloning repo: " + repo)
    execute_remote_command(ssh, "git clone " + repo, verbose = config.verbose)

    # Transfer experiment commands
    LOG.info("Transferring experiment commands from " + config.worker + "...")
    cmd = ["scp", config.user + "@" + config.worker + ":" + config.configfile_path, "."]
    execute_local_command(ssh, cmd, "initializaRemoteServer", verbose = config.verbose)

    # Gather system specs
    LOG.info("Gathering machine specs...")
    execute_remote_command(ssh, "uname -r >results/specs.txt")

    LOG.info("Running initialization script...")
    execute_remote_command(ssh, "cd test-experiments && bash initialize.sh", verbose = config.verbose)

    # Reboot to clean state and then check if successful
    #reboot(ssh, config.worker)

    ssh.close()

# run in either random or fixed order n times, rebooting between each run
def run_remote_experiment(sshC, order, exp_dict, n_runs):
    data = []
    exps = list(exp_dict.keys())

    # begin exp loop n times
    # set seed (default epoch time or provided param by user) in for loop and save number as metadata
    for x in range(n_runs):
        ssh = open_ssh_connection(sshC)
        id = uuid.uuid1()

        LOG.info("Running " + order + " loop " + str(x + 1) + " of " + str(n_runs))

        if order == "random":
            random.shuffle(exps)
        for i, exp in enumerate(exps):
            cmd = exp_dict.get(exp)
            LOG.info("Running " + cmd + "...")
            result = execute_remote_command(ssh, "cd test-experiments && " + cmd, verbose = config.verbose)
            #TODO: print out to log, look into most efficient way to add to list
            exp_result = [id, x+1, n_runs, cmd, exp, i, order, result]
            data.append(exp_result)

        #reboot(ssh, config.worker)
        ssh.close()
    return data

def insert_failure(nodename):
    pass

def main():
    # Parse Arguments:
    # hostname, username, keyfile, number of repetitions,
    # git repo, destinstion directory

    sshC = RemoteClient(config.worker, 22, config.user, config.keyfile)
    initialize_remote_server(sshC, config.repo , config.configfile_path, config.results_dir)

    # get exp cmds
    with open(config.configfile) as f:
        exps = f.readlines()
    exps = [x.strip() for x in exps]

    # assign number to each item in list
    exp_dict = {i : exps[i] for i in range(0, len(exps))}

    # run experiments, returns lists to add to dataframe
    fixed = run_remote_experiment(sshC, "fixed", exp_dict, 1)
    random = run_remote_experiment(sshC, "random", exp_dict, 1)

    # scp results directory from remote and rename with timestamp
    ssh = open_ssh_connection(sshC)
    cmd = ["scp", "-r", config.user + "@" + config.worker + ":" + config.results_dir, "."]
    execute_local_command(ssh, cmd, verbose = config.verbose)
    # timestamp results folder
    filename = datetime.now().strftime("%Y%m%d_%H:%M:%S") + "_results"
    execute_local_command(ssh, ["mv", "results", filename], verbose = config.verbose)

    # put in list, add to dataframe
    with open(filename + "/" + config.results_file) as f:
        results = f.readlines()
    all_results = [x.strip() for x in results]

    # Create dataframe for csv
    # Add start and end time
    results = pd.DataFrame(fixed + random, columns=("run_uuid", "run_num", "total_runs", "exp_command", "exp_number", "order_number", "order_type", "completion_status"))
    results["result"] = all_results

    # copy env_info.sh and run

    results.to_csv(filename + "/results.csv", index=False)
    ssh.close()

# Entry point of the application
if __name__ == "__main__":
    main()
else:
    print("Error, cannot enter main, exiting.")
    sys.exit(2)
