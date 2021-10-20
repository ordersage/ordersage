# system libraries
import sys
import os
import subprocess
import argparse
import io
from contextlib import redirect_stdout
from pathlib import Path
import glob

# Time libraries and RNG
import time
from time import sleep
import datetime
from timeit import default_timer as timer
import random

# SSH libraries
import paramiko
from scp import SCPClient

# error handling and logging
from requests import ConnectionError
import logging
from logger import configure_logging

# Subprocess functions
from subprocess import Popen, PIPE, STDOUT, run

# dataframe libraries and stats
import pandas as pd
import numpy as np
from statistics import mean

# uuid library
import uuid

# multithreading
import threading

# files from tool repo
import config
from allocation import Allocation
from toolstats import run_stats

# Config file parsing
from configparser import ConfigParser

class ThreadWithReturn(threading.Thread):
    def run(self):
        self.exec = None
        try:
            super().run()
        except BaseException as e:
            self.exec = e

    def join(self):
        threading.Thread.join(self)
        if self.exec:
            raise self.exec

# See debug info from paramiko
logging.getLogger("paramiko").setLevel(logging.DEBUG)
LOG = configure_logging(name="main", filter = True, debug = config.verbose, \
                    to_console = True, filename = "mainlogfile.log")

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
def open_ssh_connection(worker, allocation, log=None, port_num=22, timeout = 25,max_tries=10):
    """ Attemps to establish an SSH connection to the specified worker node.
    If successful, returns an SSHClient with open connection to the worker.
    """
    if log is None:
        log = LOG
    log.info("Starting ssh connection to " + worker)
    n_tries = 0
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # SSH Connect
    while True:
        try:
            ssh.connect(hostname = worker, port = port_num,
                        username = allocation.user,
                        key_filename = allocation.public_key,
                        timeout = timeout)
        except Exception as e:
            n_tries += 1
            log.error("In open_ssh_connection: " + repr(e) + " - " + str(e))
            log.info("Error #" + str(n_tries) + " of " + str(max_tries) + ".")
            if n_tries >= max_tries:
                log.error("Failure to connect to " + worker)
                log.error(e)
                raise
            else:
                log.info("Retrying...")
                sleep(timeout)
        else:
            log.info("SSH connection to " + worker + " successful.")
            return ssh

######################################
### Execute command on worker node ###
######################################
def execute_remote_command(ssh_client, cmd, max_tries=5, timeout=10,
                            print_to_console=False, log=None, test = False):
    """ Executes command on worker node via pre-established SSHClient.
    Captures stdout continuously as command runs and blocks until remote command
    finishes execution and exit status is received. If verbose option is on, stdout
    will print to terminal.
    """
    n_tries = 0
    if log is None:
        log = LOG

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
                    else:
                        # Split by newline
                        out = out.splitlines()
                        for o in filter(None, out):
                            log.debug(o)
        except Exception as e:
            n_tries += 1
            log.error("SSH exception while executing '" + cmd + "'. Attempt "
                        + str(n_tries) + " of " + str(max_tries))
            if n_tries >= max_tries:
                log.error("Connection error. Failed to execute " + cmd, exc_info = True)
                log.error(e)
                raise
            else:
                log.info("Retrying...")
                sleep(timeout)
        else:
            # Blocks until command finishes execution
            exit_status = channel.recv_exit_status()
            # Handles errors on remote side
            if exit_status != 0:
                log.error("Error executing command: '" + cmd
                            + "'. Exit status: " + str(exit_status))
                raise
            channel.close()
            return

###############################
### Execute command locally ###
###############################
def execute_local_command(cmd, function_name="execute_local_command", max_tries=1,
                        log=None):
    """ Runs commands locally, and captures stdout and stderr. If config.verbose
    is true, stdout will print to terminal.
    """
    n_tries = 0
    if log is None:
        log=LOG
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
            log.error("Exception while executing '" + " ".join(cmd)
                        + "'. Attempt " + str(n_tries) + " of "
                        + str(max_tries))
            log.error(str(ex))
            if n_tries >= max_tries:
                log.critical("Failed to execute '" + " ".join(cmd) + "'")
                return "Failure"
            else:
                log.info("Retrying...")
        else:
            break
    return "Success"

##########################
### Reset worker node ###
##########################
def reset(ssh_client, worker, log=None):
    """ Reboots worker node then checks periodically if it is back up. If
    config.reset is False, it will skip this command (for debugging only)
    """
    n_tries = 0
    max_tries = 8
    if log is None:
        log = LOG

    # Skip reboot
    if(config.reset == False):
        return "Success"

    LOG.info("Rebooting...")

    try:
        execute_remote_command(ssh_client, "sudo reboot")
    except:
        log.info('Exception on sudo reboot... assuming reboot in progress')

    # Spin until the e comes up and is ready for SSH
    log.info("Awaiting completion of reboot for "
                + worker
                + ", sleeping for 2 minutes...")
    sleep(120)

    while True:
        try:
            out = run(["nc", "-z", "-v", "-w5", worker, "22"],
                    stderr=STDOUT,
                    stdout=PIPE)
        except Exception as ex:
            log.critical(ex)
            raise
        else:
            if out.returncode == 0:
                break
            else:
                n_tries += 1
                if n_tries >= max_tries:
                    log.critical("Failed to reconnect to " + worker)
                    raise
                else:
                    log.error("Connection attempt to "
                                + worker
                                + " timed out, retrying (" + str(n_tries)
                                + " out of " + str(max_tries) + ")...")
                    sleep(60)

    LOG.info("Node " + worker + " is up at " + str(datetime.date.today()))

##############################
### Initialize worker node ###
##############################
def initialize_remote_server(repo, worker, allocation, log=None):
    """ Sets up worker node to begin running tests. Clones experiment
    repo, runs initialization script, and facilitates collectin of e
    specs. e will then be reset to a clean state to begin experimentation
    """
    max_tries = 3
    n_tries = 0

    if log is None:
        log = LOG

    log.info("Initializing " + worker)
    # Attemp to connect to server, and quit if failed
    try:
        ssh = open_ssh_connection(worker, allocation, log = log)
    except:
        log.critical('Faiure to connect on initialization of ' + worker +
                        '. Exiting...')
        raise

    try:
        # Clone experimets repo
        log.info("Cloning repo: " + repo + "...")
        execute_remote_command(ssh, "git clone " + repo, log = log)

        # Run initialization script. Results directory will be created here
        log.info("Running initialization script...")
        execute_remote_command(ssh, config.init_script_call, log = log)

        # Gather e specs
        log.info("Transferring env_info.sh to " + worker)
        cmd = ["scp",
                "-o", "StrictHostKeyChecking=no",
                "env_info.sh",
                config.user + "@" + worker + ":" + config.results_dir]
        execute_local_command(cmd, "initialize_remote_server", log = log)
        execute_remote_command(ssh, "cd " + config.results_dir + " && ./env_info.sh",
                                    log = log)
        execute_remote_command(ssh, "cd " + config.results_dir + " && mv env_out.csv "
                                    + worker + "_env_out.csv", log = log)
    except:
        log.critical('Failed to run initialization script for ' + worker +
                        '. Exiting...')
        raise

    # Reset to clean state
    try:
        reset(ssh, worker)
    except:
        log.critical(worker + " failed to reset...exiting.")
        raise

    ssh.close()

######################
### Access wrapper ###
######################
def access_provider_wrapper(args):
    if args.cloudlab:
        LOG.info("Using CloudLab as a platform for running experiments")
        return access_cloudlab(args)
    else:
        LOG.info("Using pre-allocate node for running experiments")
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
###      Release Cloudlab's resources      ###
##############################################
def release_cloudlab(args, allocation):
    deallocate_nodes(allocation, LOG)
    LOG.info("Done deallocating nodes on CloudLab.")

#####################################################
### sets up node and returns list of tests ####
#####################################################
def coordinate_initialization(allocation):
    if(len(allocation.hostnames) == 1):
        try:
            initialize_remote_server(config.repo, allocation.hostnames[0], allocation)
        except:
            sys.exit(2)
    elif len(allocation.hostnames) > 1:
        # Initialize worker nodes
        threads = [None] * len(allocation.hostnames)
        for n, host in enumerate(allocation.hostnames):
            t_log = configure_logging("main.Thread." + str(n), debug=config.verbose, filename=host+".log")
            threads[n] = ThreadWithReturn(target = initialize_remote_server,
                                          args = (config.repo, host, allocation, t_log,),
                                          name = host)
            threads[n].start()

        for t in threads:
            try:
                t.join()
            except:
                # Remove if error was caught
                allocation.hostnames.remove(t.name)
    else:
        LOG.error("Something went wrong. No nodes allocated")
        raise ValueError()

    # If all nodes failed, exit
    if len(allocation.hostnames) == 0:
        LOG.critical('All nodes failed to initialize. Exiting...')
        sys.exit(2)

    # Pick first allocation to retrieve test command list
    ssh = open_ssh_connection(allocation.hostnames[0], allocation)
    # Call function to print list of tests and direct to stdout
    LOG.info("Retrieving test commands from " + allocation.hostnames[0] + "...")
    f = io.StringIO()
    with redirect_stdout(f):
        try:
            execute_remote_command(ssh, config.exp_script_call,
                                    print_to_console=True)
        except:
            LOG.critical('Failed to retrieve test commands...exiting.')
            sys.exit(2)
    tests = f.getvalue()
    tests = tests.splitlines()
    tests = list(filter(None, tests))
    ssh.close()
    return tests

#################################################################
### Run remote tests on worker node and record metadata ###
#################################################################
def run_remote_experiment(worker, allocation, test_dict, n_runs, directory,log=None):
    """ Runs tests on worker node in either a fixed, arbitrary order or
    a random order. Runs will be executed 'n_runs' times, and results will be saved
    on the worker end. Upon completion, each run and its metadata will be stored.
    """
    test_data = []
    run_data = []
    run_times = []
    est_remaing_time = 0
    n_runs = n_runs * 2

    # add random runs to fixed calculation
    tests = list(test_dict.keys())
    if log is None:
        log = LOG
    # Set seed
    rand_seed = config.seed if config.seed else time.time()
    random.seed(rand_seed)

    # Begin runs n times
    for x in range(n_runs):

        id = uuid.uuid1()
        ssh = open_ssh_connection(worker, allocation, log)
        if config.interleave:
            order = 'fixed' if x % 2 == 0 else 'random'
        else:
            order = 'fixed' if x < (n_runs / 2) else 'random'
        log.info("Running loop " + str(x + 1) + " of " + str(n_runs) + " in " + order + " order.")

        if x > 0:
            est_time_remaining = mean(run_times) * (n_runs - x)
            est_time_remaining = str(datetime.timedelta(seconds=est_time_remaining))
            log.info('\033[1m' + 'ESTIMATED TIME REMAINING: ' + est_time_remaining + '\033[0m')

        if order == "random":
            ordered_tests = random.sample(tests, len(tests))
        else:
            ordered_tests = tests

        run_start = timer()
        # Run each command provided by user
        for i, test in enumerate(ordered_tests):
            # Get test command from dictionary
            cmd = test_dict.get(test)
            log.info("Running " + cmd + "...")
            start = time.process_time()
            try:
                execute_remote_command(ssh, "cd %s && %s" % (directory, cmd), log = log)
            except KeyboardInterrupt:
                sys.exit(2)
            except:
                result = "Failure"
            else:
                result = "Success"
            stop = time.process_time()
            # Save test with completion status and metadata
            test_result = [id, worker, x, n_runs, cmd, test, i, order, start, stop, result]
            test_data.append(test_result)
        # Collect run information
        run_stop = timer()
        run_results = [id, worker, x, n_runs, order, rand_seed, run_start, run_stop]
        run_data.append(run_results)
        try:
            reset(ssh, worker)
        except:
            log.warning('Worker ' + worker + 'failed to reset after run ' +\
                        x + ' of ' + n_runs + '. Ending ' + order + ' run early.')
            break

        ssh.close()
        run_stop_r = timer()
        run_times.append(run_stop_r - run_start)

    return test_data,run_data

#########################################################
###      Workflow for single-node experimentation      ###
#########################################################
def run_single_node(worker, allocation, results_dir, tests, timestamp, log=None):
    if log is None:
        log = LOG
    log.info("Beginning experimentation for " + worker)

    # Assign number to each test and store in dictionary
    test_dict = {i : tests[i] for i in range(0, len(tests))}

    # Extract name of dir where repo code whill be cloned (i.e. lowest-level dir in path)
    repo_dir = Path(config.repo).name
    repo_dir = repo_dir[:-len(".git")] if repo_dir.endswith(".git") else repo_dir

    # Run tests, returns lists to add to dataframe
    test_results, run_results = run_remote_experiment(worker, allocation, test_dict, config.n_runs,
                                                 directory=repo_dir, log=log)

    # Create dataframe of individual tests for csv
    test_results_csv = pd.DataFrame(test_results,
                                    columns=("run_uuid", "hostname", "run_num", "total_runs",
                                            "test_command", "test_number", "order_number",
                                            "order_type", "time_start", "time_stop",
                                            "completion_status"))
    run_results_csv = pd.DataFrame(run_results,
                                    columns=("run_uuid", "hostname", "run_num", "total_runs",
                                            "order_type", "random_seed", "time_start",
                                            "time_stop"))

    # Add machine type to results file
    ssh = open_ssh_connection(worker, allocation, log = log)
    results_with_hostname = worker + "_" + config.results_file
    try:
        execute_remote_command(ssh, "cd " + config.results_dir + " && "
                                + "mv " + config.results_file + " "
                                + results_with_hostname)
    except:
        log.warning('Failed to rename results file from ' + config.results_file +\
                    ' to ' + results_with_hostname)
    ssh.close()

    # scp everything in results directory from worker and rename with timestamp
    log.info("Transferring results from " + worker + " to local")
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
    log.info("Adding results to test metadata")
    test_results_csv["result"] = results
    test_results_csv.to_csv(results_dir + "/" + worker + "_test_results.csv", index=False)
    run_results_csv.to_csv(results_dir + "/" + worker + "_run_results.csv", index=False)

    # Move repo to new directory with timestamped name
    ssh = open_ssh_connection(worker, allocation, log = log)
    try:
        execute_remote_command(ssh, 'mv ' + repo_dir + ' ' + timestamp + '_' + repo_dir)
    except:
        log.warning('Experiment repo on ' + worker + ' unsuccessfully moved to ' +\
                    repo_dir + ' ' + timestamp + '_' + repo_dir +
                    '. Please delete or change before re-running controller.py')
    ssh.close()

    log.info("Experiemnt completed on node (%s) and stored" % worker)

##################################################################
### Workflow for experimentation using multiple-nodes #############
##################################################################
def run_multiple_nodes(allocation, results_dir, tests, timestamp):
    threads = [None] * len(allocation.hostnames)

    for n, host in enumerate(allocation.hostnames):
        t_log = configure_logging("main.Thread." + str(n), debug=config.verbose, filename=host+".log")
        threads[n] = ThreadWithReturn(target=run_single_node,
                                      args=(host, allocation,
                                            results_dir, tests, timestamp, t_log,),
                                            name=host)
        threads[n].start()

    for t in threads:
        t.join()

def concat_results(results_dir, timestamp, file_pattern, concat_name):
    df = pd.concat(map(pd.read_csv, glob.glob(os.path.join(results_dir, file_pattern))))
    df.to_csv(results_dir + "/" + timestamp + concat_name, index=False)
    return df

#####################
### Main function ###
#####################
def main():
    args = parse_args()

    # Allocate resources according to provided arguments
    allocation = access_provider_wrapper(args)

    # Set up results directory with timestamp
    LOG.info("Setting up local results directory")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H:%M:%S")
    results_dir = timestamp + "_results"
    execute_local_command(["mkdir", results_dir])

    # Initialize each node and retrieve list of commands to run tests
    test_commands = coordinate_initialization(allocation)

    if len(allocation.hostnames) == 1:
        worker = allocation.hostnames[0]
        run_single_node(worker, allocation, results_dir, test_commands, timestamp)
    elif len(allocation.hostnames) > 1:
        run_multiple_nodes(allocation, results_dir, test_commands, timestamp)
    else:
        LOG.error("Something went wrong. No nodes allocated")
    # Save all results to single file
    all_tests = concat_results(results_dir, timestamp,
                '*_test_results.csv', "_all_test_results.csv")
    all_runs = concat_results(results_dir, timestamp,
                '*_run_results.csv', "_all_run_results.csv")
    all_envs = concat_results(results_dir, timestamp,
                '*_env_out.csv', "_all_env_out.csv")

    # Run statistical analysis
    run_stats(all_tests, results_dir, timestamp)

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
