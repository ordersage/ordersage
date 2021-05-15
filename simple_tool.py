# Steps for simple example:

# On controller node:
# 1. Run orchestration script
# 2. Parse arguments
# 3. Establish connection to pre-allocated machine
# 4. Get remote server ready for experiments
#       a. Install packages, clone repo,
#          set up directory for results, reboot to clean state

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
# *Function for rebooting? How to check for reboot completion.

def parseArgs():
    pass

# Looking at libraries like paramiko to execute a single cmd or list of commands
# Does it make sense in parts of the script to invoke a shell to use stdin/out
# channels multiple times in one connection?
def openSSHConnection(hostname, username, portnum, keypath):
    pass

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
    pass
