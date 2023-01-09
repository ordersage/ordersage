"""
Configure Perf Instrumentation
"""

init_script_call = "cd instrumentation/perf && bash perf_setup.sh"
wrapper_script = "/bin/bash $HOME/instrumentation/perf/perf_wrapper.sh"
results_location = "~/perf_results"

perf_counters = "task-clock, duration_time, cycles, inst_retired.any, bus-cycles, cache-misses," \
    "cache-references, branch-misses, mem-loads, mem-stores, LLC-load-misses, LLC-store-misses," \
    "L1-dcache-load-misses, L1-icache-load-misses, dTLB-load-misses, dTLB-store-misses, page-faults," \
    "alignment-faults, context-switches, cpu-migrations, major-faults, minor-faults, branch-load-misses," \
    "iTLB-load-misses, node-store-misses, node-load-misses"

env_vars = {
    "PERF_COUNTERS_STR": perf_counters
}