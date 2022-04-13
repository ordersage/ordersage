#!/bin/bash

declare -a perf_counters=("task-clock" "duration_time" "cycles" "inst_retired.any" "bus-cycles" "cache-misses" "cache-references" "branch-misses" "mem-loads" "mem-stores" "LLC-load-misses" "LLC-store-misses" "L1-dcache-load-misses" "L1-icache-load-misses" "dTLB-load-misses" "dTLB-store-misses" "page-faults" "alignment-faults" "context-switches" "cpu-migrations" "major-faults" "minor-faults" "branch-load-misses" "iTLB-load-misses" "node-store-misses" "node-load-misses")
printf -v strcounters '%s,' "${perf_counters[@]}"
mkdir -p $HOME/perf_results
sudo perf stat -x, -o $HOME/perf_results/perf.txt -e ${strcounters%,} -- "$@"

header="run_uuid,timestamp"

for val in ${perf_counters[@]}; do
	line="${line},$(grep \,${val} $HOME/perf_results/perf.txt | cut -d, -f 1,5 )"
	header="${header},${val},${val} Percentage"
done

pfilename="perf_stats.csv"
if [[ ! -f $HOME/perf_results/$pfilename ]]; then
    echo "$header" > $HOME/perf_results/$pfilename
fi
echo "$line" >> $HOME/perf_results/$pfilename