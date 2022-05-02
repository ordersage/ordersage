#!/bin/bash

if [[ -z "${PERF_COUNTERS_STR}" ]]; then
	IFS=', ' read -r -a perf_counters <<< "$PERF_COUNTERS_STR"
else
  declare -a perf_counters=("task-clock" "duration_time" "cycles" "inst_retired.any" "bus-cycles" "cache-misses" "cache-references" "branch-misses" "mem-loads" "mem-stores" "LLC-load-misses" "LLC-store-misses" "L1-dcache-load-misses" "L1-icache-load-misses" "dTLB-load-misses" "dTLB-store-misses" "page-faults" "alignment-faults" "context-switches" "cpu-migrations" "major-faults" "minor-faults" "branch-load-misses" "iTLB-load-misses" "node-store-misses" "node-load-misses")
fi

printf -v strcounters '%s,' "${perf_counters[@]}"
mkdir -p $HOME/perf_results

echo "Running task with perf instrumentation."
echo "Modified command is: 'sudo perf stat -x, -o $HOME/perf_results/perf.txt -e ${strcounters%,} -- $@'"
sudo perf stat -x, -o $HOME/perf_results/perf.txt -e ${strcounters%,} -- "$@"

header="run_uuid,timestamp"

line="${RUN_ID},${TIMESTAMP}"
for val in ${perf_counters[@]}; do
	line="${line},$(grep \,${val} $HOME/perf_results/perf.txt | cut -d, -f 1,5 )"
	header="${header},${val},${val} Percentage"
done

header="${header},order,test_id"

pfilename="perf_stats.csv"
if [[ ! -f $HOME/perf_results/$pfilename ]]; then
    echo "$header" > $HOME/perf_results/$pfilename
fi
line="${line},${ORDER},${TEST_NUM}"
echo "$line" >> $HOME/perf_results/$pfilename