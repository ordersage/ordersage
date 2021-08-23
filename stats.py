import sys
import numpy as np
import datetime as dt
import pandas as pd
import glob
import statistics as stat
import scipy.stats as stats

#TODO:
#       exclude runs that had a failure 
#       test each node individually, then together and compare results
#       Configuration: group_by should include HW type
#       configure CI testing
#       produce a report of statistical results

def epoch2human(epoch):
  return dt.datetime.fromtimestamp(epoch).strftime('%Y-%m-%d %H:%M:%S')

time = sys.argv[1]
"""##Fetching Data"""
df_exp = pd.read_csv(glob.glob(time + "_results/*_all_exp_results.csv")[0])
df_runs = pd.read_csv(glob.glob(time + "_results/*_all_run_results.csv")[0])
df_env = pd.read_csv(glob.glob(time + "_results/*_all_env_out.csv")[0])

"""##Preprocessing"""
# Split by rand vs seq
df_exp_rand = df_exp[df_exp['order_type'] == 'random']
df_exp_seq = df_exp[df_exp['order_type'] == 'fixed']
"""##SHAPIRO WILK TEST"""

def SW_test(df,measure,columns):
  #columns = ["hw_type", "testname", "dvfs", "socket_num","MT"]
  df_cols = ['S-W Test', 'length'] + columns
  shapiro_wilk = pd.DataFrame(columns=df_cols) #This defines a dataframe that contains the pvalues and the configuration information along with number of datapoints per config

  for key, grp in df.groupby(columns):
      #if(len(grp)>=50):
      shapiro_wilk.loc[len(shapiro_wilk)] = [stats.shapiro(grp[measure])[1], len(grp), key]

  print(shapiro_wilk)
  Not_normal = shapiro_wilk[shapiro_wilk["S-W Test"]<0.05]
  Num_config_not_normal = len(Not_normal)
  Num_config_normal= len(shapiro_wilk)-len(Not_normal)
  fraction_not_normal= len(Not_normal)/len(shapiro_wilk)
  shapiro_stats = [Num_config_not_normal,Num_config_normal,fraction_not_normal]

  return shapiro_wilk, shapiro_stats

#seq data
shapiro_wilk_seq, shapiro_stats = SW_test(df_exp_seq,"result", ["exp_command"])

print("Number of configurations not normally distributed", shapiro_stats[0])
print("Number of configurations normally distributed", shapiro_stats[1])
print("Fraction of configurations not normally distributed", shapiro_stats[2])

#rand data
shapiro_wilk_rand, shapiro_stats = SW_test(df_exp_rand,"result", ["exp_command"])
print("Number of configurations not normally distributed", shapiro_stats[0])
print("Number of configurations normally distributed", shapiro_stats[1])
print("Fraction of configurations not normally distributed", shapiro_stats[2])

"""#Does Order Matter

##Function to calculate p-val and effect size for each setting
"""

def percent_difference(v_experiment,v_control):
  return ((v_experiment.mean() - v_control.mean()) / v_control.mean()) * 100

def effect_size_eta_squared_KW(v_experiment, v_control):
  """
  Returns the ets_sqared measure for effect size calculated for the KW test
  For details see: http://www.tss.awf.poznan.pl/files/3_Trends_Vol21_2014__no1_20.pdf
  (Chose eta_squared over the epsilon squared since it is the more popular method)
  """
  H = stats.kruskal(v_experiment,v_control)[0]
  k = 1
  n = len(v_experiment) + len(v_control)
  return ((H-k + 1)/(n-k))

def calc_main(df,measure):
  # Samples with fewer than this number of values will not be considered
  sample_count_thresh = 50

  configuration_key = ["exp_command"]
  df_effect = pd.DataFrame(columns = configuration_key + ["P_Diff","effect_size_KW", "Kruskal_p"])

  for idx, grp in df.groupby(configuration_key):
    random_sample = grp[grp.order_type == "random"][measure].values
    random_sample = random_sample.astype(np.float64)
    seq_sample = grp[grp.order_type == "fixed"][measure].values
    seq_sample = seq_sample.astype(np.float64)

    # if (len(random_sample) >= sample_count_thresh) and (len(seq_sample) >= sample_count_thresh): #WHEN SUFFICIENT DATA IS PRESENT
    df_effect.loc[len(df_effect)] = [idx, percent_difference(random_sample,seq_sample), effect_size_eta_squared_KW(random_sample,seq_sample), stats.kruskal(random_sample, seq_sample)[1]]

  return(df_effect)

"""##Does order affect Benchmarks"""
df_all = df_exp_seq.append(df_exp_rand)
df_effect = calc_main(df_all,"result")

#calculating average percentage difference
df_effect["abs_P_Diff"] = df_effect["P_Diff"].apply(abs)
print(sum(df_effect["abs_P_Diff"].values)/ len(df_effect))

def func(row):
  if(row["P_Diff"]>0):
    return "positive"
  else:
    return "negative"

#Looking at whether the random or the sequential order performed better

df_effect["Pos_or_Neg"] = df_effect.apply(lambda row: func(row), axis=1)
print(df_effect)
tmp = df_effect[df_effect["Kruskal_p"]< 0.05]
neg =  tmp[tmp["Pos_or_Neg"]== "negative"]
pos = tmp[tmp["Pos_or_Neg"]== "positive"]
pos_neg = pd.DataFrame(columns=["Num_seq_better_rand","Median","90th","Num_rand_better_seq","neg_Median","neg_90th"])
pos_neg.loc[len(pos_neg)] = [len(neg),stat.median(neg["abs_P_Diff"].values), neg["abs_P_Diff"].quantile(0.9),len(pos),stat.median(pos["abs_P_Diff"].values),pos["abs_P_Diff"].quantile(0.9)]
print(pos_neg)

# """#Exploring sequences in detail
#
# ##Extracting the necessary data
# """
#
# cpu_test = ["LU","CG","UA","MG","FT","BT","EP","SP","IS"]
# def check_test(name):
#   if(name in cpu_test):
#     return 1
#   else:
#     return 0
#
# mem_t = ["add", "add_omp","read_memory_loop_omp" , "write_memory_rep_stosq_omp" , "read_memory_rep_lodsq"  , "write_memory_sse_omp" , "write_memory_loop_omp" , "write_memory_loop" , "write_memory_avx_omp" , "read_memory_sse_omp" , "write_memory_memset_omp" , "write_memory_nontemporal_avx"  , "write_memory_rep_stosq" , "read_memory_rep_lodsq_omp" , "read_memory_prefetch_avx_omp" , "read_memory_loop" , "read_memory_avx_omp" , "write_memory_nontemporal_avx_omp" , "read_memory_sse" , "read_memory_prefetch_avx" , "read_memory_avx" , "write_memory_sse" , "write_memory_avx" , "write_memory_nontemporal_sse_omp" , "write_memory_nontemporal_sse", "write_memory_memset"]
#
# x = mem_cpu["random_ops"].head(1)
# for i in x:
#   print(i)
#
# def is_nan(x):
#     return (x != x)
#
# mem_key = dict({"rx": "read_memory_rep_lodsq", "rl": "read_memory_loop" , "rs": "read_memory_sse", "rv": "read_memory_avx", "rvn": "read_memory_prefetch_avx" , "wl": "write_memory_loop", "wx": "write_memory_rep_stosq" , "ws": "write_memory_sse", "wsn": "write_memory_nontemporal_sse" , "wv": "write_memory_avx", "wvn": "write_memory_nontemporal_avx" , "wm": "write_memory_memset", "orx": "read_memory_rep_lodsq_omp" , "orl": "read_memory_loop_omp" , "ors": "read_memory_sse_omp" , "orv": "read_memory_avx_omp", "orvn": "read_memory_prefetch_avx_omp" , "owl": "write_memory_loop_omp" , "owx": "write_memory_rep_stosq_omp" , "ows": "write_memory_sse_omp" , "owsn": "write_memory_nontemporal_sse_omp" , "owv": "write_memory_avx_omp" , "owvn": "write_memory_nontemporal_avx_omp" , "owm": "write_memory_memset_omp"})
#
# import re
# mem_cpu = mem_with_random.append(cpu_with_random)
# mem_cpu =mem_cpu.reset_index(drop=True)
#
# tmem_cpu = pd.DataFrame()
# whitelist = set('abcdefghijklmnopqrstuvwxyz')
#
# for idx,grp in mem_cpu.groupby("run_uuid"):
#   a = grp.random_ops.values[0]
#
#   if(is_nan(a)):
#     continue
#
#   a = a[1:(len(a)-1)]
#   a = a.split("), ")
#   tmp_a = []
#   flag = 0
#   param = []
#   if "membench" in a[0]:
#
#     mem_temp = a[0].split()
#     mem_test =  ''.join(filter(whitelist.__contains__, mem_temp[3]))
#     mem_test = mem_key.get(mem_test,"NaN")
#     flag = 1
#
#   elif "stream" in a[0]:
#     flag = 1
#     if "ST" in a[0]:
#       mem_test = "add"
#     else:
#       mem_test = "add_omp"
#
#   else:
#     continue
#
#   if flag and "npb" in a[1]:
#
#     cpu_temp =  a[1].split(",")
#     cpu_test =  ''.join(filter(whitelist.__contains__, cpu_temp[1]))
#     cpu_test = cpu_test.upper()
#     if(cpu_temp[3][2]== '0'):
#       dvfs = "no"
#     else:
#       dvfs = "yes"
#     if(cpu_temp[2][2]== 'MT'):
#       thread = 1
#     else:
#       thread = 0
#       param = [dvfs,int(cpu_temp[4][2]),thread]
#   else:
#     flag = 0
#
#   c = 0
#
#   if(flag):
#       ind = grp.loc[(grp["testname"]== cpu_test) & (grp["socket_num"] == param[1]) & (grp["dvfs"]== param[0]) & (grp["MT"]== param[2])].index.tolist()
#       tmem_cpu = tmem_cpu.append(mem_cpu.loc[ind])
#       tmem_cpu.at[tmem_cpu.index[-1], 'random_ops']  = str(tmp_a)
#       tmem_cpu.at[tmem_cpu.index[-1],'TEST'] = mem_test
#
# display(len(tmem_cpu))
#
# baseline2 = {}
# for idx, grp in cpu_with_random.groupby("testname"):
#   baseline2[idx] = stat.stdev(grp["exec_time"].values)
#
#
# cpu_t = sorted(baseline2.items(), key=lambda x: x[1])
#
# """##Plotting the performance"""
#
# accurate_mem_cpu = tmem_cpu
#
# #The red dotted line is the mean of all the execution times in the data set(cpu_with_random) of the
# #particular CPU test the graph represents
#
# df_vals = pd.DataFrame(columns=["Testname","Test","mean","diff_mean","median","no_of_datapoints"])
#
# for idx in cpu_t:
#   grp = accurate_mem_cpu[accurate_mem_cpu["testname"]==idx[0]]
#   fig, (ax) = plt.subplots(1, 1, figsize=(16,4))
#   grp1 = cpu_with_random[cpu_with_random["testname"]==idx[0]]
#   data = pd.DataFrame(columns=["TEST","Vals"])
#   overall_mean = stat.mean(grp1.exec_time.values)
#
#   for i in grp["TEST"].unique():
#     for j in list(grp[grp["TEST"]==i]["exec_time"].values):
#       data.loc[len(data)] = [i,j]
#     current_mean = grp[grp["TEST"]==i]["exec_time"].mean(axis=0)
#     diff = overall_mean -current_mean
#     df_vals.loc[len(df_vals)] = [idx[0], i, current_mean, diff , stat.median(d),len(d)]
#
#   #plotting the data
#   ax = sns.swarmplot(x="TEST", y="Vals", data=data, size=3)
#   ax.set_xticklabels(ax.get_xticklabels(), rotation=90)
#   ax.set_title((idx[0]))
#   ax.axhline(overall_mean, ls='-.',color = 'r')
#   ax.set_ylabel("execution time")
#   plt.show();
#   print("\n\n")
#   print("\n\n \t\t\t\t\t\t-------NEXT CPU TEST-------- \n")
#
# """##Analysing"""
#
# df_vals["abs_diff_mean"] = df_vals["diff_mean"].apply(abs)
# df_vals = df_vals.sort_values("abs_diff_mean",ascending= False)
#
# #Here for each CPU test, I select the memory test(i.e the memory test after hwich this cpu test runs)
# #that differs the furthest from the mean value of execution time of the cpu test
#
#
# maxtest = []
# for idx,grp in df_vals.groupby("Testname"):
#   maxtest.append((idx,grp.Test.values[0],grp.abs_diff_mean.values[0],grp.no_of_datapoints.values[0]))
#
#
# for i in maxtest:
#   print(i,"\n")
#
# """#TESTING#"""
