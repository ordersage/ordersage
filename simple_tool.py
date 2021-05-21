# Steps for simple example:

# On controller node:
# 1. Run orchestration script
# 2. Parse arguments
# 3. Establish connection to pre-allocated machine
# 4. Get remote server ready for experiments
#       a. clone repo, set up directory for results
#       b. run initialize.sh
#           - install libraries,
#       b2. gather machine specs (specs.sh) save under results
#       c. reboot to clean state
# On remote machine (facilitated by controller node)
# 5. Run loop n times:
#   a. Run experiments in fixed order
#   b. Store results in directory
#   c. Reboot
# 6. Run loop n times:
#   a. Run experiments in random order
#   b. Store results in directory
#   c. Reboot
# 7. scp results directory to controller node

# On controller node:
# 8. Insert results into database

# *Eventually add in stats tests to tell if order matters

# todo: loops, recognize experiments

# system libraries
import sys
import argparse

# Time libraries and RNG
from time import sleep
import datetime
import random

# SSH libraries
import paramiko
from scp import SCPClient

# Subprocess functions
from subprocess import Popen,PIPE,STDOUT,call

# Configuration file
import config

# will update, possibly create class with open connection, send command,
# read stdout, etc
class SSHConnection():
    def __init__(self, server, portnum, uname, keyfile):
        self.server = server
        self.portnum = portnum
        self.uname = uname
        self.keypath = keyfile

def parseArgs():
    pass

# currently returns SSHClient obj, not sure best method here
# Look into how to handle passphrases
def openSSHConnection(sshC):
    ssh = paramiko.SSHClient()
    sshkey = paramiko.Ed25519Key.from_private_key_file(sshC.keypath)
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # SSH Connect
    nTries = 0
    maxTries = 3
    while True:
        try:
            # here in ochestration.py, a transport and channel are open. Is it needed here?
            ssh.connect(hostname = sshC.server, port = sshC.portnum, username = sshC.uname, pkey = sshkey)
        except Exception as e:
            nTries += 1
            print("In openSSHConnection: " + repr(e) + " - " + str(e))
            print("Error #" + str(nTries) + " out of " + str(maxTries) + ".")
            if nTries >= maxTries:
                return "Failure"
            else:
                sleep(10)
                print("\tRetrying...")
        else:
            print("SSH connection to " + sshC.server + " successful.")
            try:
                return ssh
            except Exception as e:
                print("In openSSHConnection: " + repr(e) + " - " + str(e))
                return "Failure"
            else:
                break

# relies on user having netcat. Would ping be better?
def checkReboot(server):
    # Spin until the machine comes up and is ready for SSH
    nTries = 0
    maxTries = 8
    print("Awaiting completion of reboot for " + server + ", sleeping for 1 minute...")
    sleep(60)
    while True:
        try:
            # hostname
            # out = Popen(["nc", "-z", "-v", "-w5", server, "22"],stderr=STDOUT,stdout=PIPE)
            out = Popen(["nc", "-z", "-v", "-w5", server, "22"],stderr=STDOUT,stdout=PIPE)
        except:
            print("In checkReboot: " + repr(e) + " - " + str(e))
            return "Failure"
        else:
            t = out.communicate()[0],out.returncode
            if t[1] == 0:
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

# Clone repo for fixed and random, set up results directory
def initializeRemoteServer(sshC, repo, dest_dir):
    ssh = openSSHConnection(sshC)

    ssh.exec_command("mkdir " + dest_dir)
    print("Cloning repo: " + repo)
    # TODO: get system specs and add to results directory
    ssh.exec_command("git clone " + repo)
    print("Running initialization script...")
    ssh.exec_command("cd test-experiments && bash initialize.sh")
    print("Rebooting...")
    ssh.exec_command("sudo reboot")
    reboot = checkReboot(config.worker)
    ssh.close()

# run in either random or fixed order n times, rebooting between each run
def runRemoteExperiment(sshC, order, nruns, results_dir):
    ssh = openSSHConnection(sshC)
    scp = SCPClient(ssh.get_transport())

    # get list of experiment files from remote server save to list
    # exps = ["exp_1.sh",  "exp_2.sh",  "exp_3.sh",  "exp_4.sh",  "exp_5.sh"]
    #for x in range(nruns):
    #    if order == "random":
    #        exps = random.shuffle(exps)
    #    for exp in exps:
            # run on remote machine
            # save results to directory

    # scp results to controller node
    scp.get(results_dir, ".")
    scp.close()
    ssh.close()

# Send results to database
def insertResults(result_dir, nodename):
    pass

def insertFailure(nodename):
    pass

def connectToDatabase(hostname, username, password, database):
    pass

def main():
    # Parse Arguments:
    # hostname, username, keyfile, number of repetitions,
    # git repo, destinstion directory

    # Create SSHConnection
    sshC = SSHConnection(config.worker, 22, config.user, config.keyfile)

    # initialize server, clone repo, reboot
    initializeRemoteServer(sshC, config.repo , "results")

    # run experiments
    runRemoteExperiment(sshC, "fixed", 1, "~/results")

# Entry point of the application
if __name__ == "__main__":
    main()
else:
    print("Error, cannot enter main, exiting.")
    sys.exit(2)
