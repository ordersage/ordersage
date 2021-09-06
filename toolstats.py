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
#       configure CI testing (waiting on code from Nikhil)
#       produce a report of statistical results

def process_data(df):
    df_exp_rand = df[df['random'] == 1]
    df_exp_seq = df[df['random'] == 0]
    return df_exp_rand, df_exp_seq

"""##SHAPIRO WILK TEST"""

def SW_test(df,measure,columns):
  #columns = ["hw_type", "testname", "dvfs", "socket_num","MT"]
  df_cols = ['S-W Test', 'length'] + columns
  shapiro_wilk = pd.DataFrame(columns=df_cols)

  for key, grp in df.groupby(columns):
      #if(len(grp)>=50):
      shapiro_wilk.loc[len(shapiro_wilk)] = [stats.shapiro(grp[measure])[1], len(grp)] + list(key)

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
    # The paper reports this as fixed-random/fixed * 100
    return ((v_control.mean() - v_experiment.mean()) / v_control.mean()) * 100

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

  # Compare between fixed and random for each configuration
  for idx, grp in df.groupby(configuration_key):
    random_sample = grp[grp.random == 1][measure].values
    random_sample = random_sample.astype(np.float64)
    seq_sample = grp[grp.random == 0][measure].values
    seq_sample = seq_sample.astype(np.float64)
    # if (len(random_sample) >= sample_count_thresh) and (len(seq_sample) >= sample_count_thresh): #WHEN SUFFICIENT DATA IS PRESENT
    df_effect.loc[len(df_effect)] = \
                    list(idx) + \
                    [percent_difference(random_sample,seq_sample),
                    effect_size_eta_squared_KW(random_sample,seq_sample),
                    stats.kruskal(random_sample, seq_sample)[1]]

  return df_effect

def pos_or_neg(row):
  if(row["P_Diff"]>0):
    return "positive"
  else:
    return "negative"

def write_sw_results(shapiro, shapiro_stats):
    normally_distributed = shapiro[shapiro["S-W Test"]>0.05]
    print(normally_distributed)
    print("Number of configurations not normally distributed", shapiro_stats[0])
    print("Number of configurations normally distributed", shapiro_stats[1])
    print("Fraction of configurations not normally distributed", shapiro_stats[2])
    print("\n\n")

def write_kw_results(df_effect):
    #calculating average percentage difference
    df_effect["abs_P_Diff"] = df_effect["P_Diff"].apply(abs)
    avg_pd = sum(df_effect["abs_P_Diff"].values) / len(df_effect)
    print("Average percent difference: %f\n\n" % avg_pd)

    # Looking at whether the random or the sequential order performed better
    print("Summary of Random vs. Sequential Performance")
    print("----------------------------------------------")
    df_effect["Pos_or_Neg"] = df_effect.apply(lambda row: pos_or_neg(row), axis=1)
    tmp = df_effect[df_effect["Kruskal_p"]<0.05]
    neg =  tmp[tmp["Pos_or_Neg"]== "negative"]
    pos = tmp[tmp["Pos_or_Neg"]== "positive"]
    performance_summary = pd.DataFrame(columns=["num_seq_outperforms",
                                                "Median",
                                                "90th",
                                                "num_rand_outperforms",
                                                "neg_Median",
                                                "neg_90th"])
    performance_summary.loc[len(performance_summary)] = \
                            [len(neg),
                            stat.median(neg["abs_P_Diff"].values),
                            neg["abs_P_Diff"].quantile(0.9),
                            len(pos),
                            stat.median(pos["abs_P_Diff"].values),
                            pos["abs_P_Diff"].quantile(0.9)]
    print(performance_summary.to_string(index=False))

def main():
    df = pd.read_csv('examples/test_data.csv')
    df_exp_rand, df_exp_seq = process_data(df)

    print("Running Shapiro-Wilk Test...\n")
    print("Sequential Data")
    print("----------------------------------------------")
    #seq data
    shapiro_wilk_seq, shapiro_stats = SW_test(df_exp_seq,"result", ["exp_command", "hostname"])
    write_sw_results(shapiro_wilk_seq, shapiro_stats)
    #rand data
    print("Random Data")
    print("----------------------------------------------")
    shapiro_wilk_rand, shapiro_stats = SW_test(df_exp_rand,"result", ["exp_command", "hostname"])
    write_sw_results(shapiro_wilk_rand, shapiro_stats)

    """##Does order affect Benchmarks"""
    print("Running Kruskal Wallis Test...")
    df_effect = calc_main(df,"result", ["exp_command", "hostname"])
    write_kw_results(df_effect)

if __name__ == "__main__":
    main()
else:
    print("Error, cannot enter main, exiting.")
    sys.exit(2)
