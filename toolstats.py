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
#           Update with new plan from 9/16
#       produce a report of statistical results
#       configure CI testing (waiting on code from Nikhil)



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

    if len(configuration_key) == 1:
        config = [idx]
    else:
        config = list(idx)
    # if (len(random_sample) >= sample_count_thresh) and (len(seq_sample) >= sample_count_thresh): #WHEN SUFFICIENT DATA IS PRESENT
    df_effect.loc[len(df_effect)] = \
                    config + \
                    [percent_difference(random_sample,seq_sample),
                    effect_size_eta_squared_KW(random_sample,seq_sample),
                    stats.kruskal(random_sample, seq_sample)[1]]  # can just calculate this once instaead of also in effect size

  return df_effect

def pos_or_neg(row):
  if(row["P_Diff"]>0):
    return "positive"
  else:
    return "negative"

def get_median(df, column):
    try:
        return stat.median(df[column].values)
    except:
        return np.nan

def get_ninety(df, column):
    try:
        return df[column].quantile(0.9)
    except:
        return np.nan

def write_kw_results(df_effect):
    #calculating average percentage difference
    df_effect["abs_P_Diff"] = df_effect["P_Diff"].apply(abs)
    avg_pd = sum(df_effect["abs_P_Diff"].values) / len(df_effect)
    print("Average percent difference: %f\n\n" % avg_pd)

    # Looking at whether the random or the sequential order performed better
    print("Summary of Random vs. Sequential Performance")
    print("----------------------------------------------")
    # column of fixed greater than random and apply ops on that
    df_effect["Pos_or_Neg"] = df_effect.apply(lambda row: pos_or_neg(row), axis=1)
    tmp = df_effect[df_effect["Kruskal_p"]<0.05]
    neg =  tmp[tmp["Pos_or_Neg"]== "negative"]
    pos = tmp[tmp["Pos_or_Neg"]== "positive"]
    # add 10th percentile
    performance_summary = pd.DataFrame(columns=["num_seq_outperforms",
                                                "seq_Median",
                                                "seq_90th",
                                                "num_rand_outperforms",
                                                "rand_Median",
                                                "rand_90th"])
    performance_summary.loc[len(performance_summary)] = \
                            [len(neg),
                            get_median(neg,"abs_P_Diff"),
                            get_ninety(neg, "abs_P_Diff"),
                            len(pos),
                            get_median(pos,"abs_P_Diff"),
                            get_ninety(pos,"abs_P_Diff")]
    print(performance_summary.to_string(index=False))
    print()
    print()
##############################################################################
def process_data(data):
    # keep for later use potentially
    return data

def run_stats(data):
    # Record single or multinode and split data by order type
    n_nodes = len(data['hostname'].unique())
    combined_stats = [] # change to dataframe after we get cols
    node_stats = [] # change to dataframe after we get cols

    if n_nodes == 1:
        print("Running stats for single node")
        print("----------------------------------------------")
        node_stats = run_group_stats(data)
    else:
        # run stats for all
        print("Running stats for combined nodes")
        print("----------------------------------------------")
        combined_stats = run_group_stats(data)
        print("Running stats for individual nodes")
        print("----------------------------------------------")
        single_node_stats = run_group_stats(data, group=['hostname','exp_command'])
        print("Comparing individual node stats with combined")
        print("----------------------------------------------")
        compare_single_nod(combined_stats, node_stats)

    # TODO Write stats data to csv

def run_group_stats(data, group=['exp_command']):
    stats = pd.DataFrame
    fixed_data = data[data['random'] == 0]
    random_data = data[data['random'] == 1]

    # Shapiro-Wilk to test for normality
    print("Running Shapiro-Wilk on fixed data")
    print("----------------------------------------------")
    shapiro_wilk_fixed, shapiro_stats_fixed = SW_test(fixed_data,"result",group)
    write_sw_results(shapiro_wilk_fixed, shapiro_stats_fixed)

    print("Running Shapiro-Wilk on random data")
    print("----------------------------------------------")
    shapiro_wilk_random, shapiro_stats = SW_test(random_data,"result",group)
    write_sw_results(shapiro_wilk_random, shapiro_stats)

    # Kruskal Wallis
    print("Running Kruskal Wallis")
    print("----------------------------------------------")
    kw_stats = calc_main(data,"result", group)
    write_kw_results(kw_stats)

    # TODO: Add in confidence interval
    return stats

"""##SHAPIRO WILK TEST"""

def SW_test(df,measure,group):
  df_cols = ['S-W test statistic','S-W p-value'] + group
  shapiro_wilk = pd.DataFrame(columns=df_cols)

  for key, grp in df.groupby(group):
      if len(columns) == 1:
          config = [key]
      else:
          config = list(key)
      shapiro_wilk.loc[len(shapiro_wilk)] = [stats.shapiro(grp[measure])[0],
                                            stats.shapiro(grp[measure])[1]]
                                            + config

  num_not_normal = len(shapiro_wilk[shapiro_wilk["S-W Test"]<0.05])
  num_normal = len(shapiro_wilk) - num_not_normal
  frac_not_normal = num_not_normal / len(shapiro_wilk)
  shapiro_stats = [num_not_normal, num_normal, frac_not_normal]

  return shapiro_wilk, shapiro_stats


  def write_sw_results(shapiro, shapiro_stats):
      normally_distributed = shapiro[shapiro["S-W Test"]>0.05]
      if len(normally_distributed) > 0:
          print(normally_distributed)
      print("Number of configurations not normally distributed", shapiro_stats[0])
      print("Number of configurations normally distributed", shapiro_stats[1])
      print("Fraction of configurations not normally distributed", shapiro_stats[2])
      print("\n\n")

def compare_single_node(combined_stats, single_stats):
    return None


def main():
    df = pd.read_csv('examples/test_data.csv')
    run_stats(df)


if __name__ == "__main__":
    main()
else:
    print("Error, cannot enter main, exiting.")
    sys.exit(2)
