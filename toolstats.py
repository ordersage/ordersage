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
    kruskall_wallace = kw_test(data,"result", group)
    write_kw_results(kruskall_wallace)

    # Effect Size
    print("Calculating percent difference")
    print("----------------------------------------------")



    # TODO: Add in confidence interval
    return stats

"""##SHAPIRO WILK TEST"""

def SW_test(df,measure,group):
  df_cols = group + ['S-W test statistic','S-W p-value']
  shapiro_wilk = pd.DataFrame(columns=df_cols)

  for key, grp in df.groupby(group):
      if len(columns) == 1:
          config = [key]
      else:
          config = list(key)
      shapiro_wilk.loc[len(shapiro_wilk)] = group +
                                            [stats.shapiro(grp[measure])[0],
                                            stats.shapiro(grp[measure])[1]]

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

def KW_test(df, measure, group):
  # Samples with fewer than this number of values will not be considered
  sample_count_thresh = 50
  kruskal_wallace = pd.DataFrame(columns = group + \
                                            ['K-W test statistic',
                                            'K-W p-value',
                                            'percent difference',
                                            'K-W effect size'])

  # Compare between fixed and random for each configuration
  for idx, grp in df.groupby(group):
    fixed_results = grp[grp.random == 0][measure].values
    fixed_results = fixed_results.astype(np.float64)
    random_results= grp[grp.random == 1][measure].values
    random_results = random_results.astype(np.float64)

    # run test and compute results
    kw_stats = stats.kruskall(fixed_results, random_results)
    p_diff = percent_difference(fixed_results, random_results)
    effect_size = effect_size_eta_squared_KW(fixed_results, random_results, kw_stats[0])

    # needed for use with group size of one or >1
    if len(group) == 1:
        config = [idx]
    else:
        config = list(idx)
    # if (len(random_sample) >= sample_count_thresh) and (len(seq_sample) >= sample_count_thresh): #WHEN SUFFICIENT DATA IS PRESENT
    kruskal_wallace.loc[len(df_effect)] = config +
                                            [kw_stats[0],
                                            kw_stats[1],
                                            p_diff,
                                            effect_size]

  return kruskal_wallace

def percent_difference(v_control, v_experiment):
    # The paper reports this as fixed-random/fixed * 100
    return ((v_control.mean() - v_experiment.mean()) / v_control.mean()) * 100

def effect_size_eta_squared_KW(v_control, v_experiment, kw_H):
  """
  Returns the ets_sqared measure for effect size calculated for the KW test
  For details see: http://www.tss.awf.poznan.pl/files/3_Trends_Vol21_2014__no1_20.pdf
  (Chose eta_squared over the epsilon squared since it is the more popular method)
  """
  k = 1
  n = len(v_experiment) + len(v_control)
  return ((kw_H-k + 1)/(n-k))


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
