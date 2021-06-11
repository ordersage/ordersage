# system libraries
import sys
import subprocess
import argparse

# Time libraries and RNG
from time import sleep
import datetime
import random

# SSH libraries
import paramiko
from scp import SCPClient

# error handling and logging
from requests import ConnectionError
import logging

# Subprocess functions
from subprocess import Popen, PIPE, STDOUT, run

# csv library
import pandas as pd

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

def parse_args():
    pass

def open_ssh_connection(sshC, timeout=10, max_tries=3):
    ssh = paramiko.SSHClient()
    # what if it is an rsa key?
    sshkey = paramiko.Ed25519Key.from_private_key_file(sshC.keypath)
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # SSH Connect
    n_tries = 0
    while True:
        try:
            ssh.connect(hostname = sshC.server, port = sshC.portnum, username = sshC.uname, pkey = sshkey, timeout = timeout)
        except Exception as e:
            n_tries += 1
            print("In open_ssh_connection: " + repr(e) + " - " + str(e))
            print("Error #" + str(n_tries) + " out of " + str(max_tries) + ".")
            if n_tries >= max_tries:
                # Do something here other than return failure. Possibly raise exception
                # Write to the log first
                raise ConnectionError("\tFailure to connect to " + sshC.server + "...exiting.")
            else:
                print("\tRetrying...")
                #sleep(10)
        else:
            print("SSH connection to " + sshC.server + " successful.")
            return ssh

#TODO: Add in retry option
def execute_remote_command(sshClient, cmd, verbose=False, max_tries=1):
    try:
        channel = sshClient.get_transport().open_session()
        channel.set_combine_stderr(True)
        channel.exec_command(cmd)
        while True:
            output = channel.recv(1024)
            if not output:
                break
            else:
                if verbose:
                    print(output.decode('utf-8').rstrip())
    except Exception as e:
        print("\tSSH exception while executing " + cmd)
        return "Failure"
    else:
        exit_status = channel.recv_exit_status()
        if exit_status != 0:
            if verbose == True:
                print("\tError executing command: " + cmd)
                print("\tExit status: " + str(exit_status))
            return "Failure"
        channel.close()
        return "Success"

#TODO: Add print option for stderr
def execute_local_command(ssh, cmd, function_name, verbose=False, max_tries=1):
    n_tries = 0
    while True:
        try:
            out = subprocess.run(cmd, stderr=STDOUT, stdout=PIPE)
        except Exception as ex:
            print("Error executing " + " ".join(cmd) + ": " + repr(ex))
        else:
            if out.returncode == 0:
                if verbose and out.stdout:
                    print(out.stdout.decode('utf-8'))
                break
            else:
                n_tries += 1
                if n_tries > max_tries:
                    return "Failure"
                else:
                    print("\tError in "+ function_name + " retrying (" + str(n_tries) + " out of " + str(max_tries) + ")...")

    return "Success"

def reboot(sshClient, server):
    print("Rebooting...")
    execute_remote_command(sshClient,"sudo reboot")

    # Spin until the machine comes up and is ready for SSH
    # Still printing to stdout...
    n_tries = 0
    max_tries = 8
    print("Awaiting completion of reboot for " + server + ", sleeping for 2 minutes...")
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
                    print("\tConnection attempt to " + server + " timed out, retrying (" + str(n_tries) + " out of " + str(max_tries) + ")...")
                    sleep(60)

    print("Node " + server + " is up at " + str(datetime.datetime.today()))
    return "Success"

#
# Initialize Remote Server
# TODO: Get system specs and save to log file
#
def initialize_remote_server(sshC, repo, config_path, dest_dir):
    ssh = open_ssh_connection(sshC)
    max_tries = 3
    n_tries = 0

    # set up results directory and clone repo
    print("Cloning repo: " + repo)
    execute_remote_command(ssh, "git clone " + repo, verbose = config.cmd_verbose)

    #Transfer experiment commands
    print("Transferring experiment commands from " + config.worker + "...")
    cmd = ["scp", config.user + "@" + config.worker + ":" + config.configfile_path, "."]
    execute_local_command(ssh, cmd, "initializaRemoteServer", verbose = config.cmd_verbose)

    print("Running initialization script...")
    execute_remote_command(ssh, "cd test-experiments && bash initialize.sh", verbose = config.cmd_verbose)

    # Reboot to clean state and then check if successful
    #reboot(ssh, config.worker)

    ssh.close()

# run in either random or fixed order n times, rebooting between each run
def run_remote_experiment(sshC, order, exps, nruns):
    data = []

    # begin exp loop ntimes
    for x in range(nruns):
        ssh = open_ssh_connection(sshC)
        runInfo = []
        results = []
        id = uuid.uuid1()

        print("Running loop " + str(x + 1) + " of " + str(nruns))
        if order == "random":
            random.shuffle(exps)
        for exp in exps:
            print("Running " + exp + "...")
            cmd = "cd test-experiments && " + exp
            results.append(execute_remote_command(ssh, cmd, verbose = config.exp_verbose))

        runInfo.extend((id, x+1, order, exps, results))
        data.append(runInfo)

        reboot(ssh, config.worker)
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

    # run experiments, returns lists to add to dataframe
    fixed = run_remote_experiment(sshC, "fixed", exps, 1)
    random = run_remote_experiment(sshC, "random", exps, 1)

    # scp results from remote experiments
    ssh = open_ssh_connection(sshC)
    cmd = ["scp", config.user + "@" + config.worker + ":" + config.results_path, "."]
    execute_local_command(ssh, cmd, "initializaRemoteServer", verbose = config.cmd_verbose)

    # put in list, add to dataframe
    with open(config.results_file) as f:
        results = f.readlines()
    results = [x.strip() for x in results]
    #TODO Add results to csv

    ssh.close()

    # Create dataframe for csv
    results = pd.DataFrame(fixed + random, columns=('run_uuid', 'run_num', 'run_type', 'experiment_order', "success?"))
    results.to_csv("test.csv", index=False)

# Entry point of the application
if __name__ == "__main__":
    main()
else:
    print("Error, cannot enter main, exiting.")
    sys.exit(2)
