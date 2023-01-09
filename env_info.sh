#!/bin/bash

#########################
### Initial Variables ###
#########################
timestamp=$(date -u +%s)
#run_uuid=$(uuidgen)
nodeid=$(cat /var/emulab/boot/nodeid)
nodeuuid=$(cat /var/emulab/boot/nodeuuid)

###############################
### Environment Information ###
###############################
echo -n "Getting Environment Information - "
date
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -y
sudo apt-get install hwinfo numactl -y
gcc_ver=$(gcc --version | grep gcc | awk '{print $4}')

# HW info, no PCI bus on ARM means lshw doesn't have as much information
nthreads=$(nproc --all)
total_mem=$(sudo hwinfo --memory | grep "Memory Size" | awk '{print $3 $4}')
arch=$(uname -m)
kernel_release=$(uname -r)
os_release=$(. /etc/os-release; echo "Ubuntu" ${VERSION/*, /})
# Because ARM has to do cpuinfo so differently, hardcode for non x86_64...
nsockets=1
if [ ${arch} == 'x86_64' ]; then
    nsockets=$(cat /proc/cpuinfo | grep "physical id" | sort -n | uniq | wc -l)
    cpu_model=$(lscpu | grep "Model name:" | awk '{print substr($0, index($0, $3))}')
    mem_clock_speed=$(sudo dmidecode --type 17  | grep "Configured Clock Speed" | head -n 1 | awk '{print $4}')
    mem_clock_speed=${mem_clock_speed}MHz
elif [ ${arch} == 'aarch64' ]; then
    cpu_model="ARMv8 (Atlas/A57)"
    mem_clock_speed="Unknown(ARM)"
else
    # Temp placeholder for unknown architecture
    cpu_model="Unknown(Unknown_Arch)"
    mem_clock_speed="Unknown(Unknown_Arch)"
fi

# Hash
version_hash=$(git rev-parse HEAD)

# Write to file
echo "timestamp,nodeid,nodeuuid,arch,ver_hash,gcc_ver,total_mem,mem_clock_speed,nthreads,nsockets,cpu_model,kernel_release,os_release" > env_out.csv
echo "$timestamp,$nodeid,$nodeuuid,$arch,$version_hash,$gcc_ver,$total_mem,$mem_clock_speed,$nthreads,$nsockets,$cpu_model,$kernel_release,$os_release" >> env_out.csv
