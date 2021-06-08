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

# Subprocess functions
from subprocess import Popen,PIPE,STDOUT,run

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

def parseArgs():
    pass

def openSSHConnection(sshC):
    ssh = paramiko.SSHClient()
    # what if it is an rsa key?
    sshkey = paramiko.Ed25519Key.from_private_key_file(sshC.keypath)
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # SSH Connect
    nTries = 0
    maxTries = 3
    while True:
        try:
            ssh.connect(hostname = sshC.server, port = sshC.portnum, username = sshC.uname, pkey = sshkey)
        except Exception as e:
            nTries += 1
            print("In openSSHConnection: " + repr(e) + " - " + str(e))
            print("Error #" + str(nTries) + " out of " + str(maxTries) + ".")
            if nTries >= maxTries:
                print("\tFailure to connect to " + sshC.server + "...exiting.")
                # Do something here other than return failure
                return "Failure"
            else:
                sleep(10)
                print("\tRetrying...")
        else:
            print("SSH connection to " + sshC.server + " successful.")
            return ssh

#TODO: Add in retry option
def execRemoteCommand(sshClient, cmd, verbose = False):
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
def execLocalCommand(ssh, cmd, methodName, maxTries = 1, verbose = False):
    nTries = 0
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
                nTries += 1
                if nTries > maxTries:
                    return "Failure"
                else:
                    print("\tError in "+ methodName + " retrying (" + str(nTries) + " out of " + str(maxTries) + ")...")

    return "Success"

def reboot(sshClient, server):
    print("Rebooting...")
    execRemoteCommand(sshClient,"sudo reboot")

    # Spin until the machine comes up and is ready for SSH
    # Still printing to stdout...
    nTries = 0
    maxTries = 8
    print("Awaiting completion of reboot for " + server + ", sleeping for 2 minutes...")
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
                nTries += 1
                if nTries > maxTries:
                    return "Failure"
                else:
                    print("\tConnection attempt to " + server + " timed out, retrying (" + str(nTries) + " out of " + str(maxTries) + ")...")
                    sleep(60)

    print("Node " + server + " is up at " + str(datetime.datetime.today()))
    return "Success"

#
# Initialize Remote Server
# TODO: Get system specs and save to log file
#
def initializeRemoteServer(sshC, repo, config_path, dest_dir):
    ssh = openSSHConnection(sshC)
    maxTries = 3
    nTries = 0

    # set up results directory and clone repo
    print("Cloning repo: " + repo)
    execRemoteCommand(ssh, "git clone " + repo, verbose = config.cmd_verbose)

    #Transfer experiment commands
    print("Transferring experiment commands from " + config.worker + "...")
    cmd = ["scp", config.user + "@" + config.worker + ":" + config.configfile_path, "."]
    execLocalCommand(ssh, cmd, "initializaRemoteServer", verbose = config.cmd_verbose)

    print("Running initialization script...")
    execRemoteCommand(ssh, "cd test-experiments && bash initialize.sh", verbose = config.cmd_verbose)

    # Reboot to clean state and then check if successful
    #reboot(ssh, config.worker)

    ssh.close()

# run in either random or fixed order n times, rebooting between each run
def runRemoteExperiment(sshC, order, exps, nruns):
    data = []

    # begin exp loop ntimes
    for x in range(nruns):
        ssh = openSSHConnection(sshC)
        runInfo = []
        results = []
        id = uuid.uuid1()

        print("Running loop " + str(x + 1) + " of " + str(nruns))
        if order == "random":
            random.shuffle(exps)
        for exp in exps:
            print("Running " + exp + "...")
            cmd = "cd test-experiments && " + exp
            results.append(execRemoteCommand(ssh, cmd, verbose = config.exp_verbose))

        runInfo.extend((id, x+1, order, exps, results))
        data.append(runInfo)

        reboot(ssh, config.worker)
        ssh.close()
    return data

def insertFailure(nodename):
    pass

def main():
    # Parse Arguments:
    # hostname, username, keyfile, number of repetitions,
    # git repo, destinstion directory

    sshC = RemoteClient(config.worker, 22, config.user, config.keyfile)
    initializeRemoteServer(sshC, config.repo , config.configfile_path, config.results_dir)

    # get exp cmds
    with open(config.configfile) as f:
        exps = f.readlines()
    exps = [x.strip() for x in exps]

    # run experiments, returns lists to add to dataframe
    fixed = runRemoteExperiment(sshC, "fixed", exps, 1)
    random = runRemoteExperiment(sshC, "random", exps, 1)

    # scp results from remote experiments
    ssh = openSSHConnection(sshC)
    cmd = ["scp", config.user + "@" + config.worker + ":" + config.results_path, "."]
    execLocalCommand(ssh, cmd, "initializaRemoteServer", verbose = config.cmd_verbose)

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
