"""
Configure Pin-to-core Instrumentation
"""

wrapper_script = "/bin/bash $HOME/instrumentation/pin_to_core/core_wrapper.sh"
number_of_cores = 1

env_vars = {
    "NUM_CORES": number_of_cores
}
