# system libraries
import sys
import os
import subprocess
import argparse

# Time libraries and RNG
import time
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

# Config file parsing
from configparser import ConfigParser

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
    formatter = logging.Formatter(frmt_str)
    console.setFormatter(formatter)
    logger.addHandler(console)

    return logger

LOG = configure_logging(debug = config.verbose, filename = "logfile.log")

def parse_args():
    parser = argparse.ArgumentParser(description='Description of supported command-line arguments:')    
    parser.add_argument('--cloudlab', action='store_true',
                        help='Switch allowing running experiments on CloudLab machines')
    parser.add_argument('--cloudlab_config', type=str, default='cloudlab.config',
                        help='Path to config file with CloudLab-related settings')
    return parser.parse_args()

def open_ssh_connection(timeout=10, max_tries=3):
    """ Attemps to establish an SSH connection to the worker node specified in
    config. If successful, returns an SSHClient with open connection to the worker.
    """
    n_tries = 0
    ssh = paramiko.SSHClient()
    # what if it is an rsa key?
    sshkey = paramiko.Ed25519Key.from_private_key_file(config.keyfile)
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # SSH Connect
    while True:
        try:
            ssh.connect(hostname = config.worker, port = config.port_num,
                        username = config.user, pkey = sshkey,
                        timeout = timeout)
        except Exception as e:
            n_tries += 1
            LOG.error("In open_ssh_connection: " + repr(e) + " - " + str(e))
            LOG.info("Error #" + str(n_tries) + " of " + str(max_tries) + ".")
            if n_tries >= max_tries:
                LOG.error("Failure to connect to " + config.worker)
                raise ConnectionError()
            else:
                LOG.info("Retrying...")
        else:
            LOG.info("SSH connection to " + config.worker + " successful.")
            return ssh

def execute_remote_command(ssh_client, cmd, max_tries=1):
    """ Executes command on worker node via pre-established SSHClient.
    Captures stdout continuously as command runs and blocks until remote command
    finishes execution and exit status is received. If verbose option is on, stdout
    will print to terminal.

    TODO: Check error handling
    """
    n_tries = 0

    while True:
        try:
            # Open channel and execute command
            transport = ssh_client.get_transport()
            channel = transport.open_session()
            channel.set_combine_stderr(True)
            channel.exec_command(cmd)

            # Capture stdout as it is received
            while True:
                output = channel.recv(1024)
                if not output:
                    break
                else:
                    out = output.decode('utf-8')
                    # Split by newline
                    out = out.splitlines()
                    for o in out:
                        LOG.debug(o)
        except Exception as e:
            n_tries += 1
            LOG.error("SSH exception while executing " + cmd)
            if n_tries >= max_tries:
                LOG.critical("Failed to execute " + cmd, exec_info = True)
                return "Failure"
            else:
                LOG.info("Retrying...")
        else:
            # Blocks until command finishes execution
            exit_status = channel.recv_exit_status()
            # Retry here as well?
            if exit_status != 0:
                LOG.error("Error executing command: " + cmd
                            + ". Exit status: " + str(exit_status))
                return "Failure"
            channel.close()
            return "Success"

#TODO: Add print option for stderr
def execute_local_command(cmd, function_name="execute_local_command", max_tries=1):
    """ Runs commands locally, and captures stdout and stderr. If config.verbose
    is true, stdout will print to terminal.

    TODO: Check error handling
    """
    n_tries = 0
    while True:
        try:
            out = subprocess.run(cmd, stderr=STDOUT, stdout=PIPE)
        except Exception as ex:
            n_tries += 1
            LOG.error("Exception while executing " + " ".join(cmd)
                        + ". Error #" + str(n_tries) + " of "
                        + str(max_tries))
            if n_tries > max_tries:
                LOG.critical("Failed to execute " + " ".join(cmd))
                return "Failure"
            else:
                LOG.info("Retrying...")
        else:
            if out.returncode == 0:
                stdout = out.stdout.decode('utf-8')
                if stdout:
                    LOG.info(out.stdout.decode('utf-8'))
                break
            else:
                LOG.error(out.stdout.decode('utf-8'))
                # Retry here?
                return "Failure"

    return "Success"

def reboot(ssh_client):
    """ Reboots worker node then checks periodically if it is back up. If
    config.reboot is False, it will skip this command (for debugging only)
    """
    n_tries = 0
    max_tries = 8

    # Skip reboot
    if(config.reboot == False):
        return "Success"

    LOG.info("Rebooting...")
    execute_remote_command(ssh_client, "sudo reboot")

    # Spin until the machine comes up and is ready for SSH
    LOG.info("Awaiting completion of reboot for "
                + config.worker
                + ", sleeping for 2 minutes...")
    sleep(120)

    while True:
        try:
            out = run(["nc", "-z", "-v", "-w5", server, "22"],stderr=STDOUT, stdout=PIPE)
        except:
            print("In reboot: " + repr(e) + " - " + str(e))
        else:
            if out.returncode == 0:
                break
            else:
                n_tries += 1
                if n_tries > max_tries:
                    LOG.critical("Failed to reconnect to " + config.worker)
                    return "Failure"
                else:
                    LOG.error("Connection attempt to "
                                + server
                                + " timed out, retrying (" + str(n_tries)
                                + " out of " + str(max_tries) + ")...")
                    sleep(60)

    LOG.info("Node " + server + " is up at " + str(datetime.today()))
    return "Success"

def initialize_remote_server(repo, worker):
    """ Sets up worker node to begin running experiments. Clones experiment
    repo, runs initialization script, and facilitates collectin of machine
    specs. Machine will then be rebooted to a clean state to begin experimentation

    TODO: Run env_info.sh remotely and save results, check return value and exit
    if unsuccessful
    """
    max_tries = 3
    n_tries = 0

    # Attemp to connect to server, and quit if failed
    try:
        ssh = open_ssh_connection()
    except:
        LOG.critical("Failure to connect to " + config.worker,
                    exec_info=True)
        quit()

    # Remove old repo if present
    repo_short = repo.split("/")[-1]
    dir_name = repo_short[:-len(".git")] if repo_short.endswith(".git") else repo_short
    LOG.info("Trying to remove old directory: " + dir_name + "...")
    execute_remote_command(ssh, "rm -rf " + dir_name)
 
    # Clone experimets repo
    LOG.info("Cloning repo: " + repo + "...")
    execute_remote_command(ssh, "git clone " + repo)

    # Transfer experiment commands
    LOG.info("Transferring experiment commands from " + config.worker + "...")
    cmd = ["scp",
            config.user + "@" + config.worker + ":" + config.configfile_path,
            "."]
    execute_local_command(cmd, "initializa_remote_server")

    # Run initialization script. Results directory will be created here
    LOG.info("Running initialization script...")
    execute_remote_command(ssh, "cd test-experiments && bash initialize.sh")

    # Gather machine specs
    # LOG.info("Transferring env_info.sh to " + config.worker)
    # cmd = ["scp",
    #         "env_info.sh",
    #         config.user + "@" + config.worker + ":" + "/users/carina"]
    # execute_local_command(cmd, "initializa_remote_server")
    # execute_remote_command("./env_info.sh")

    # Reboot to clean state
    reboot(ssh)

    ssh.close()

def run_remote_experiment(order, exp_dict, n_runs):
    """ Runs experiments on worker node in either a fixed, arbitrary order or
    a random order. Runs will be executed 'n_runs' times, and results will be saved
    on the worker end. Upon completion, each run and its metadata will be stored.

    TODO: Create second csv with uuid and metadata
    """
    exp_data = []
    run_data = []
    exps = list(exp_dict.keys())

    # Begin exp loop n times
    for x in range(n_runs):
        rand_seed = int(time.time())
        id = uuid.uuid1()
        ssh = open_ssh_connection()

        LOG.info("Running " + order + " loop " + str(x + 1) + " of " + str(n_runs))
        if order == "random":
            random.seed(rand_seed)
            random.shuffle(exps)

        run_start = time.process_time()
        # Run each command provided by user
        for i, exp in enumerate(exps):
            # Get experiment command from dictionary
            cmd = exp_dict.get(exp)
            LOG.info("Running " + cmd + "...")
            start = time.process_time()
            result = execute_remote_command(ssh, "cd test-experiments && " + cmd)
            stop = time.process_time()
            # Save experiment with completion status and metadata
            exp_result = [id, x, n_runs, cmd, exp, i, order, start, stop, result]
            exp_data.append(exp_result)
        # Collect run information
        run_stop = time.process_time()
        run_results = [id, x, n_runs, order, rand_seed, run_start, run_stop]
        run_data.append(run_results)

        reboot(ssh)
        ssh.close()
    return exp_data,run_data

def access_provider_wrapper(args):
    if args.cloudlab:
        LOG.info("Using CloudLab as a platform for running experiments")
        access_cloudlab(args)
    else:
        LOG.info("Using pre-allocate machine for running experiments")

def access_cloudlab(args, timeout=10):
    config_parser = ConfigParser() 
    config_parser.read(args.cloudlab_config)
    
    try:
        hostname = config_parser.get("DEFAULT", "hostname")
        port_num = config_parser.get("DEFAULT", "port_num")
        user = config_parser.get("DEFAULT", "user")
        keyfile = config_parser.get("DEFAULT", "keyfile")
    except Exception as e:
        LOG.error("Bad CloudLab config file: required option is missing")
        raise ValueError()
    
    sshkey = paramiko.Ed25519Key.from_private_key_file(keyfile)

    try:
        cloudlab_ssh = paramiko.SSHClient()
        cloudlab_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cloudlab_ssh.connect(hostname=hostname, port=port_num,
                             username=user, pkey=sshkey,
                             timeout=timeout)
    except:
        LOG.error("Cannot establish ssh access to CloudLab platform")
        raise ConnectionError()
    else:
        LOG.info("Established ssh access to CloudLab platform")

def main():
    args = parse_args() 

    access_provider_wrapper(args)

    # Set up worker node
    initialize_remote_server(config.repo, config.worker)

    # Read in commands to run experiments
    config_file = os.path.basename(config.configfile_path)
    with open(config_file) as f:
        exps = f.readlines()
    exps = [x.strip() for x in exps]
    # Assign number to each experiment and store in dictionary
    exp_dict = {i : exps[i] for i in range(0, len(exps))}

    # Run experiments, returns lists to add to dataframe
    fixed_exp, fixed_run = run_remote_experiment("fixed", exp_dict, 1)
    random_exp, random_run = run_remote_experiment("random", exp_dict, 1)

    # Create dataframe of individual experiments for csv
    exp_results_csv = pd.DataFrame(fixed_exp + random_exp,
                                columns=("run_uuid", "run_num", "total_runs",
                                        "exp_command", "exp_number", "order_number",
                                        "order_type", "time_start", "time_stop",
                                        "completion_status"))
    run_results_csv = pd.DataFrame(fixed_run + random_run,
                                columns=("run_uuid", "run_num", "total_runs",
                                        "order_type", "random_seed", "time_start",
                                        "time_stop"))

    # scp results directory from worker and rename with timestamp
    ssh = open_ssh_connection()
    cmd = ["scp", "-r", config.user + "@" + config.worker + ":" + config.results_dir, "."]
    execute_local_command(cmd)

    # Timestamp results folder
    results_dir = datetime.now().strftime("%Y%m%d_%H:%M:%S") + "_results"
    execute_local_command(["mv", "results", results_dir])

    # Gather results
    with open(results_dir + "/" + config.results_file) as f:
        results = f.readlines()
    results = [x.strip() for x in results]

    # Add results to dataframe and save as csv
    exp_results_csv["result"] = results
    exp_results_csv.to_csv(results_dir + "/experiment_results.csv", index=False)
    run_results_csv.to_csv(results_dir + "/run_results.csv", index=False)
    ssh.close()

# Entry point of the application
if __name__ == "__main__":
    main()
else:
    print("Error, cannot enter main, exiting.")
    sys.exit(2)
