# system libraries
import sys
import os
import subprocess
import argparse
import io
from contextlib import redirect_stdout

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

# multithreading
import threading

# files from tool repo
import config
from allocation import Allocation

# Config file parsing
from configparser import ConfigParser

# See debug info from paramiko
logging.getLogger("paramiko").setLevel(logging.DEBUG)

########################
### Configure Log file ###
########################
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

# Optional code for integration with CloudLab
try:
    from cloudlab_allocator.orchestration import parse_config, \
        allocate_nodes, deallocate_nodes
    LOG.debug("Imported code for CloudLab integration.")
except:
    LOG.debug("Unable to import code for CloudLab integration. Proceeding without it.")

######################################
### Parse arguments to application ###
######################################
def parse_args():
    parser = argparse.ArgumentParser(description='Description of supported command-line arguments:')
    parser.add_argument('--cloudlab', action='store_true',
                        help='Switch to allowing running experiments on CloudLab es')
    parser.add_argument('--cloudlab_config', type=str, default='cloudlab.config',
                        help='Path to config file with CloudLab-related settings')
    return parser.parse_args()

################################
### Establish SSH Connection ###
################################
def open_ssh_connection(worker, allocation, port_num = 22, timeout=10, max_tries=10):
    """ Attemps to establish an SSH connection to the specified worker node.
    If successful, returns an SSHClient with open connection to the worker.
    """
    LOG.info("Starting to open ssh connection")
    n_tries = 0
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # SSH Connect
    while True:
        try:
            ssh.connect(hostname = worker, port = port_num,
                        username = allocation.user,
                        key_filename = allocation.public_key, timeout = timeout)
        except Exception as e:
            n_tries += 1
            LOG.error("In open_ssh_connection: " + repr(e) + " - " + str(e))
            LOG.info("Error #" + str(n_tries) + " of " + str(max_tries) + ".")
            if n_tries >= max_tries:
                LOG.error("Failure to connect to " + worker)
                raise ConnectionError()
            else:
                LOG.info("Retrying...")
        else:
            LOG.info("SSH connection to " + worker + " successful.")
            return ssh

######################################
### Execute command on worker node ###
######################################
def execute_remote_command(ssh_client, cmd, max_tries=1, timeout=10,
                            print_to_console=False):
    """ Executes command on worker node via pre-established SSHClient.
    Captures stdout continuously as command runs and blocks until remote command
    finishes execution and exit status is received. If verbose option is on, stdout
    will print to terminal.
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
                    if print_to_console:
                        print(out)
                    # Split by newline
                    out = out.splitlines()
                    for o in filter(None, out):
                        LOG.debug(o)
        except Exception as e:
            n_tries += 1
            LOG.error("SSH exception while executing '" + cmd + "'. Attempt "
                        + str(n_tries) + " of " + str(max_tries))
            if n_tries >= max_tries:
                LOG.critical("Failed to execute " + cmd, exc_info = True)
                return "Failure"
            else:
                LOG.info("Retrying...")
                sleep(timeout)
        else:
            # Blocks until command finishes execution
            exit_status = channel.recv_exit_status()
            # Here is where errors on the remote side are handled
            # Retry here as well?
            if exit_status != 0:
                LOG.error("Error executing command: '" + cmd
                            + "'. Exit status: " + str(exit_status))
                return "Failure"
            channel.close()
            return "Success"

###############################
### Execute command locally ###
###############################
def execute_local_command(cmd, function_name="execute_local_command", max_tries=1):
    """ Runs commands locally, and captures stdout and stderr. If config.verbose
    is true, stdout will print to terminal.
    """
    n_tries = 0
    while True:
        try:
            out = subprocess.run(cmd, stderr=STDOUT, stdout=PIPE)
            stdout = out.stdout.decode('utf-8')
            stdout = stdout.splitlines()
            # Print stdout
            for o in filter(None, stdout):
                LOG.debug(o)
            # Raises exception if exit status is non-zero
            out.check_returncode()
        except Exception as ex:
            n_tries += 1
            LOG.error("Exception while executing '" + " ".join(cmd)
                        + "'. Attempt " + str(n_tries) + " of "
                        + str(max_tries))
            LOG.error(str(ex))
            if n_tries >= max_tries:
                LOG.critical("Failed to execute '" + " ".join(cmd) + "'")
                return "Failure"
            else:
                LOG.info("Retrying...")
        else:
            break
    return "Success"

##########################
### Reboot worker node ###
##########################
def reboot(ssh_client, worker):
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

    # Spin until the e comes up and is ready for SSH
    LOG.info("Awaiting completion of reboot for "
                + worker
                + ", sleeping for 2 minutes...")
    sleep(120)

    while True:
        try:
            out = run(["nc", "-z", "-v", "-w5", worker, "22"],
                    stderr=STDOUT,
                    stdout=PIPE)
        except Exception as ex:
            print("In reboot: " + repr(ex) + " - " + str(ex))
        else:
            if out.returncode == 0:
                break
            else:
                n_tries += 1
                if n_tries >= max_tries:
                    LOG.critical("Failed to reconnect to " + worker)
                    return "Failure"
                else:
                    LOG.error("Connection attempt to "
                                + worker
                                + " timed out, retrying (" + str(n_tries)
                                + " out of " + str(max_tries) + ")...")
                    sleep(60)

    LOG.info("Node " + worker + " is up at " + str(datetime.today()))
    return "Success"

##############################
### Initialize worker node ###
##############################
def initialize_remote_server(repo, worker, allocation):
    """ Sets up worker node to begin running experiments. Clones experiment
    repo, runs initialization script, and facilitates collectin of e
    specs. e will then be rebooted to a clean state to begin experimentation
    """
    max_tries = 3
    n_tries = 0

    # Attemp to connect to server, and quit if failed
    try:
        ssh = open_ssh_connection(worker, allocation)
    except:
        LOG.critical("Failure to connect to " + worker,
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

    # Run initialization script. Results directory will be created here
    LOG.info("Running initialization script...")
    execute_remote_command(ssh, config.init_script_call)

    # Gather e specs
    LOG.info("Transferring env_info.sh to " + worker)
    cmd = ["scp",
            "-o", "StrictHostKeyChecking=no",
            "env_info.sh",
            config.user + "@" + worker + ":" + config.results_dir]
    execute_local_command(cmd, "initialize_remote_server")
    execute_remote_command(ssh, "cd " + config.results_dir + " && ./env_info.sh")
    # Rename to add hostname
    execute_remote_command(ssh, "cd " + config.results_dir + " && mv env_out.csv "
                                + worker + "_env_out.csv")

    # Reboot to clean state
    reboot(ssh, worker)

    ssh.close()

#################################################################
### Run remote experiments on worker node and record metadata ###
#################################################################
def run_remote_experiment(worker, allocation, order, exp_dict, n_runs):
    """ Runs experiments on worker node in either a fixed, arbitrary order or
    a random order. Runs will be executed 'n_runs' times, and results will be saved
    on the worker end. Upon completion, each run and its metadata will be stored.
    """
    exp_data = []
    run_data = []
    exps = list(exp_dict.keys())

    # Set seed
    rand_seed = config.seed if config.seed else time.time()
    random.seed(rand_seed)

    # Begin exp loop n times
    for x in range(n_runs):
        id = uuid.uuid1()
        ssh = open_ssh_connection(worker, allocation)

        LOG.info("Running " + order + " loop " + str(x + 1) + " of " + str(n_runs))
        if order == "random":
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
            exp_result = [id, worker, x, n_runs, cmd, exp, i, order, start, stop, result]
            exp_data.append(exp_result)
        # Collect run information
        run_stop = time.process_time()
        run_results = [id, worker, x, n_runs, order, rand_seed, run_start, run_stop]
        run_data.append(run_results)

        reboot(ssh, worker)
        ssh.close()
    return exp_data,run_data

######################
### Access wrapper ###
######################
def access_provider_wrapper(args):
    if args.cloudlab:
        LOG.info("Using CloudLab as a platform for running experiments")
        return access_cloudlab(args)
    else:
        LOG.info("Using pre-allocate e for running experiments")
        return Allocation(config.workers, user = config.user,
                          public_key = config.keyfile)

##############################################
### Access Cloudlab and allocate resources ###
##############################################
def access_cloudlab(args):
    config_parser = ConfigParser()
    config_parser.read(args.cloudlab_config)

    try:
        site = config_parser.get("HARDWARE", "site")
        hw_type = config_parser.get("HARDWARE", "hw_type")
        node_count = int(config_parser.get("HARDWARE", "node_count"))
    except Exception as e:
        LOG.error("Bad CloudLab config file: required option is missing")
        raise ValueError()

    user, project, certificate, private_key, public_key, geni_cache = \
        parse_config(args.cloudlab_config)

    LOG.info("Starting to allocate nodes on CloudLab.")
    allocation = allocate_nodes(node_count, site, hw_type, \
                                user, project, certificate, \
                                private_key, public_key, geni_cache, \
                                LOG)
    LOG.info("Done allocating nodes on CloudLab. Hostnames: " + \
             str(allocation.hostnames))
    return allocation

#########################
### Release resources ###
#########################
def release_resources_wrapper(args, allocation):
    if args.cloudlab:
        LOG.info("Calling CLoudLab's function for releasing resources")
        release_cloudlab(args, allocation)
    else:
        pass

##############################################
### Release Cloudlab's resources #############
##############################################
def release_cloudlab(args, allocation):
    deallocate_nodes(allocation, LOG)
    LOG.info("Done deallocating nodes on CloudLab.")

#########################################################
###      Workflow for single-node experimentation      ###
#########################################################
def run_single_node(worker, allocation, results_dir):

    # Set up worker node
    initialize_remote_server(config.repo, worker, allocation)

    ssh = open_ssh_connection(worker, allocation)
    # There might be a better way to do this...
    # Call function to print list of experiments and direct to stdout
    LOG.info("Retrieving experiment commands" + worker + "...")
    f = io.StringIO()
    with redirect_stdout(f):
        execute_remote_command(ssh, config.experiment_script_call,
                                print_to_console=True)
    exps = f.getvalue()
    exps = exps.splitlines()
    exps = list(filter(None, exps))


    # Assign number to each experiment and store in dictionary
    exp_dict = {i : exps[i] for i in range(0, len(exps))}

    # Run experiments, returns lists to add to dataframe
    fixed_exp, fixed_run = run_remote_experiment(worker, allocation, "fixed", exp_dict, 1)
    random_exp, random_run = run_remote_experiment(worker, allocation, "random", exp_dict, 1)

    # Create dataframe of individual experiments for csv
    exp_results_csv = pd.DataFrame(fixed_exp + random_exp,
                                columns=("run_uuid", "hostname", "run_num", "total_runs",
                                        "exp_command", "exp_number", "order_number",
                                        "order_type", "time_start", "time_stop",
                                        "completion_status"))
    run_results_csv = pd.DataFrame(fixed_run + random_run,
                                columns=("run_uuid", "hostname", "run_num", "total_runs",
                                        "order_type", "random_seed", "time_start",
                                        "time_stop"))

    # Add machine type to results file
    results_with_hostname = worker + "_" + config.results_file
    execute_remote_command(ssh, "cd " + config.results_dir + " && "
                            + "mv " + config.results_file + " "
                            + results_with_hostname)
    ssh.close()

    # scp everything in results directory from worker and rename with timestamp
    LOG.info("Transferring results from " + worker + " to local")
    # "-o StrictHostKeyChecking=no" is supposed to help avoid answering "yes" for new machines
    cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-r",
            config.user + "@" + worker + ":" + config.results_dir + "/*",
            "./" + results_dir]
    execute_local_command(cmd)

    # Gather results
    with open(results_dir + "/" + results_with_hostname) as f:
        results = f.readlines()
    results = [x.strip() for x in results]

    # Add results to dataframe and save as csv specific to host
    LOG.info("Adding results to experiment metadata")
    exp_results_csv["result"] = results
    exp_results_csv.to_csv(results_dir + "/" + worker + "_experiment_results.csv", index=False)
    run_results_csv.to_csv(results_dir + "/" + worker + "_run_results.csv", index=False)

    LOG.info("Experiemnts successfully run on single node (%s) and stored" % worker)

##################################################################
### Workflow for experimentation using multiple-nodes #############
##################################################################
def run_multiple_nodes(allocation, results_dir):
    threads = [None] * len(allocation.hostnames)
    for n, host in enumerate(allocation.hostnames):
        threads[n] = threading.Thread(target=run_single_node,
                                        args=(host, allocation, results_dir,))
        threads[n].start()

    for t in threads:
        t.join()

#####################
### Main function ###
#####################
def main():
    args = parse_args()

    # Allocate resources according to provided arguments
    allocation = access_provider_wrapper(args)
    timestamp = datetime.now().strftime("%Y%m%d_%H:%M:%S")

    # Set up results directory with timestamp
    results_dir = timestamp + "_results"
    execute_local_command(["mkdir", results_dir])

    if len(allocation.hostnames) == 1:
        worker = allocation.hostnames[0]
        run_single_node(worker, allocation, results_dir)
    elif len(allocation.hostnames) > 1:
        run_multiple_nodes(allocation, results_dir)
    else:
        LOG.error("Something went wrong. No nodes allocated")

    # Releasing allocated resources
    release_resources_wrapper(args, allocation)

######################################
### Entry point of the application ###
######################################
if __name__ == "__main__":
    main()
else:
    print("Error, cannot enter main, exiting.")
    sys.exit(2)
