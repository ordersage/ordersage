# install perf
sudo apt-get install -y linux-tools-common linux-tools-generic linux-tools-`uname -r`
sudo su -c 'echo -e "kernel.perf_event_paranoid = -1" >> /etc/sysctl.conf'