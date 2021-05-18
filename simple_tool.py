# Steps for simple example:

# On controller node:
# 1. Run orchestration script
# 2. Parse arguments
# 3. Establish connection to pre-allocated machine
# 4. Get remote server ready for experiments
#       a. clone repo, set up directory for results
#       b. run initialization script
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
#7. sftp results directory to controller node

# On controller node:
# 8. Insert results into database

# *Eventually add in stats tests to tell if order matters

# system libraries
import sys
import argparse

# Time libraries
from time import sleep
import datetime

# SSH library
import paramiko

# Subprocess functions
from subprocess import Popen,PIPE,STDOUT,call

def parseArgs():
    pass


def sendRemoteCommand(server, uname, portnum, keypath, cmmd):
    ssh = paramiko.SSHClient()
    sshkey = paramiko.Ed25519Key.from_private_key_file(keypath)
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # SSH Connect
    nTries = 0
    maxTries = 3
    while True:
        try:
            # here in ochestration.py, a transport and channel are open. Is it needed here?
            ssh.connect(hostname = server, port = portnum, username = uname, pkey = sshkey)
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
            print("SSH connection to " + server + " successful.")
            try:
                # open session and return the channel
                stdin, stdout, stderr = ssh.exec_command(cmmd)
                # does it make sense to return these values?
            except Exception as e:
                print("In openSSHConnection: " + repr(e) + " - " + str(e))
                return "Failure"
            else:
                break

    # close connection
    ssh.close()


def checkReboot(server):
    # Spin until the machine comes up and is ready for SSH
    nTries = 0
    maxTries = 8
    print("Awaiting completion of reboot for " + server + ", sleeping for 4 minutes...")
    sleep(240)
    while True:
        try:
            out = Popen(["nc", "-z", "-v", "-w5", server, "22"],stderr=STDOUT,stdout=PIPE)
        except:
            print("In rebootRemoteServer: " + repr(e) + " - " + str(e))
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
def initializeRemoteServer(repo, dest_dir):
    pass

# run in either random or fixed order n times, rebooting between each run
def runRemoteExperiment(is_fixed, nruns):
    pass

# Send results to database
def insertResults(result_dir, nodename):
    pass

def insertFailure(nodename):
    pass

def connectToDatabase(hostname, username, password, database):
    pass

def main():
    sendRemoteCommand("ms0745.utah.cloudlab.us", "carina", 22, "/home/carina/.ssh/id_cloud", "sudo reboot")
    reboot = checkReboot("ms0745.utah.cloudlab.us")
    if reboot == "Success":
        print("Success")

# Entry point of the application
if __name__ == "__main__":
    main()
else:
    print("Error, cannot enter main, exiting.")
    sys.exit(2)
