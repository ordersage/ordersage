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

# SSH library
import paramkio

# Subprocess functions
from subprocess import Popen,PIPE,STDOUT,call

def parseArgs():

def openSSHConnection(hostname, username, portnum, keypath):
    ssh = paramiko.SSHClient()
    sshkey = paramiko.RSAKey.from_private_key_file(keypath)
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # SSH Connect
    nTries = 0
    maxTries = 3
    while True:
        try:
            ssh.connect(hostname = hostname, port = portnum, username = username, pkey = sshkey)
        except Exception as e:
            nTries += 1
            print "In openSSHConnection: " + repr(e) + " - " + str(e)
            print "Error #" + str(nTries) + " out of " + str(maxTries) + "."
            if nTries >= maxTries:
                return "Failure"
            else:
                sleep(10)
                print "\tRetrying..."
        else:
            print "SSH connection to " + hostname + " successful."
            try:
                # open session and return the channel
                transport = ssh.get_transport()
                return transport.open_session()
            except Exception as e:
                print "In openSSHConnection: " + repr(e) + " - " + str(e)
                return "Failure"
            else:
                break


def checkReboot(hostname):
    # Spin until the machine comes up and is ready for SSH
    nTries = 0
    maxTries = 8
    print "Awaiting completion of reboot for " + hostname + ", sleeping for 4 minutes..."
    sleep(240)
    while True:
        try:
            out = Popen(["nc", "-z", "-v", "-w5", server, "22"],stderr=STDOUT,stdout=PIPE)
        except:
            print "In rebootRemoteServer: " + repr(e) + " - " + str(e)
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
                    print "\tConnection attempt to " + hostname + " timed out, retrying (" + str(nTries) + " out of " + str(maxTries) + ")..."
                    sleep(60)

    print "Node " + hostname + " is up at " + str(datetime.datetime.today()) + ", connecting via SSH."
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
    openSSHConnection("ms0745.utah.cloudlab.us", 22, "carina", )


# Entry point of the application
if __name__ == "__main__":
    main()
else:
    print "Error, cannot enter main, exiting."
    sys.exit(2)
