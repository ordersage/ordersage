if [[ -z "${NUM_CORES}" ]]; then
	NUM_CORES=1
fi

all_cpus=()
cpu_count=$(nproc --all)
for ((i=0; i<$cpu_count; i++))
do 
	all_cpus+=($((2**$i)))
done

selected_cpu=0
for ((i=0; i<$NUM_CORES; i++))
do 
	curr_cpu=${all_cpus[ $RANDOM % ${#all_cpus[@]} ]}
	all_cpus=( "${all_cpus[@]/$delete}" )
	selected_cpu=$(($selected_cpu + $curr_cpu))
done
selected_cpu=$(printf '0x%x\n' $selected_cpu)

echo "Running task on CPU(s) with taskset. Mask: $selected_cpu"
echo "Modified command is: 'taskset $selected_cpu $@'"

taskset $selected_cpu "$@"