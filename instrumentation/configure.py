from importlib import import_module
from scp import SCPClient

from importlib import import_module


def configure_instr_module(ssh_execute, module_name, env_dict, log):
    config = import_module("instrumentation." + module_name + ".config")
    if hasattr(config, "env_vars"):
        log.info("Configuring environment variables for " + module_name)
        env_dict.update(config.env_vars)
    if hasattr(config, 'init_script_call'):
        log.info("Executing init script: " + config.init_script_call)
        ssh_execute(config.init_script_call)
    if hasattr(config, 'wrapper_script'):
        intrumentation_wrapper = env_dict.get("INSTRUMENT", "")
        intrumentation_wrapper += " " + config.wrapper_script
        env_dict["INSTRUMENT"] = intrumentation_wrapper


def setup_env_file(ssh, env_dict):
    with open("temp_env.txt", "w") as fp:
        for key, value in env_dict.items():
            fp.write("export " + key + "=" + "\"%s\"" % value + "\n")
    scp = SCPClient(ssh.get_transport())
    scp.put("temp_env.txt", "~/instr_env.txt")


def pull_results(ssh, module_name, result_dir, log):
    config = import_module("instrumentation." + module_name + ".config")
    if hasattr(config, "results_location"):
        log.info("Pulling results from " + config.results_location)
        scp = SCPClient(ssh.get_transport())
        scp.get(config.results_location, result_dir, recursive=True)
