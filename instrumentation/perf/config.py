"""
Configure Perf Instrumentation
"""

init_script_call = "cd instrumentation/perf && bash perf_setup.sh"
wrapper_script = "/bin/bash $HOME/instrumentation/perf/perf_wrapper.sh"
