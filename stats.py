import sys
import numpy as np
import datetime as dt
import pandas as pd
import glob
import statistics as stat
import scipy.stats as stats

#TODO:
#       get data set with known results for testing
#       exclude runs that had a failure
#       test each node individually, then together and compare results
#       Configuration: group_by should include HW type
#           listresources command for CL, look into others
#       configure CI testing (waiting on code from Nikhil)
#       produce a report of statistical results

"""##SHAPIRO WILK TEST"""

def SW_test(df,measure,columns):
  #columns = ["hw_type", "testname", "dvfs", "socket_num","MT"]
  df_cols = ['S-W Test', 'length'] + columns
  shapiro_wilk = pd.DataFrame(columns=df_cols) #This defines a dataframe that contains the pvalues and the configuration information along with number of datapoints per config

  for key, grp in df.groupby(columns):
      #if(len(grp)>=50):
      shapiro_wilk.loc[len(shapiro_wilk)] = [stats.shapiro(grp[measure])[1], len(grp)] + list(key)

  print(shapiro_wilk)
  Not_normal = shapiro_wilk[shapiro_wilk["S-W Test"]<0.05]
  Num_config_not_normal = len(Not_normal)
  Num_config_normal= len(shapiro_wilk)-len(Not_normal)
  fraction_not_normal= len(Not_normal)/len(shapiro_wilk)
  shapiro_stats = [Num_config_not_normal,Num_config_normal,fraction_not_normal]

  return shapiro_wilk, shapiro_stats

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

def calc_main(df,measure, configuration_key):
  # Samples with fewer than this number of values will not be considered
  sample_count_thresh = 50
  df_effect = pd.DataFrame(columns = configuration_key + ["P_Diff","effect_size_KW", "Kruskal_p"])

  for idx, grp in df.groupby(configuration_key):
    random_sample = grp[grp.order_type == "random"][measure].values
    random_sample = random_sample.astype(np.float64)
    seq_sample = grp[grp.order_type == "fixed"][measure].values
    seq_sample = seq_sample.astype(np.float64)

    # if (len(random_sample) >= sample_count_thresh) and (len(seq_sample) >= sample_count_thresh): #WHEN SUFFICIENT DATA IS PRESENT
    df_effect.loc[len(df_effect)] = [idx, percent_difference(random_sample,seq_sample), effect_size_eta_squared_KW(random_sample,seq_sample), stats.kruskal(random_sample, seq_sample)[1]]

  return(df_effect)

def func(row):
  if(row["P_Diff"]>0):
    return "positive"
  else:
    return "negative"

time = sys.argv[1]
"""##Fetching Data"""
df_exp = pd.read_csv(glob.glob(time + "_results/*_all_exp_results.csv")[0])
df_runs = pd.read_csv(glob.glob(time + "_results/*_all_run_results.csv")[0])
df_env = pd.read_csv(glob.glob(time + "_results/*_all_env_out.csv")[0])

"""##Preprocessing"""
# Split by rand vs seq
df_exp_rand = df_exp[df_exp['order_type'] == 'random']
df_exp_seq = df_exp[df_exp['order_type'] == 'fixed']

#seq data
shapiro_wilk_seq, shapiro_stats = SW_test(df_exp_seq,"result", ["exp_command", "hostname"])

print("Number of configurations not normally distributed", shapiro_stats[0])
print("Number of configurations normally distributed", shapiro_stats[1])
print("Fraction of configurations not normally distributed", shapiro_stats[2])

#rand data
shapiro_wilk_rand, shapiro_stats = SW_test(df_exp_rand,"result", ["exp_command", "hostname"])
print("Number of configurations not normally distributed", shapiro_stats[0])
print("Number of configurations normally distributed", shapiro_stats[1])
print("Fraction of configurations not normally distributed", shapiro_stats[2])

"""##Does order affect Benchmarks"""
df_all = df_exp_seq.append(df_exp_rand)
df_effect = calc_main(df_all,"result", ["exp_command", "hostname"])

#calculating average percentage difference
df_effect["abs_P_Diff"] = df_effect["P_Diff"].apply(abs)
print(sum(df_effect["abs_P_Diff"].values)/ len(df_effect))

# Looking at whether the random or the sequential order performed better

df_effect["Pos_or_Neg"] = df_effect.apply(lambda row: func(row), axis=1)
print(df_effect)
tmp = df_effect[df_effect["Kruskal_p"]< 0.05]
neg =  tmp[tmp["Pos_or_Neg"]== "negative"]
pos = tmp[tmp["Pos_or_Neg"]== "positive"]
pos_neg = pd.DataFrame(columns=["Num_seq_better_rand","Median","90th","Num_rand_better_seq","neg_Median","neg_90th"])
pos_neg.loc[len(pos_neg)] = [len(neg),stat.median(neg["abs_P_Diff"].values), neg["abs_P_Diff"].quantile(0.9),len(pos),stat.median(pos["abs_P_Diff"].values),pos["abs_P_Diff"].quantile(0.9)]
print(pos_neg)
