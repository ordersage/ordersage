import sys
import numpy as np
import datetime as dt
import pandas as pd
import glob
import statistics as stat
import scipy.stats as stats

#TODO:
#       exclude runs that had a failure
#       produce a report of statistical results
#       configure CI testing (waiting on code from Nikhil)

##############################################################################
def process_data(data):
    # keep for later use potentially
    return data

def run_stats(data):
    # Record single or multinode and split data by order type
    n_nodes = len(data['hostname'].unique())

    if n_nodes == 1:
        print("Running stats for single node")
        print("----------------------------------------------")
        node_stats, summary = run_group_stats(data)
        node_stats.to_csv('node_stats.csv', index=False)
        # TODO Write stats data to csv
    else:
        # run stats for all
        print("Running stats for combined nodes")
        print("----------------------------------------------")
        combined_stats, summary_all = run_group_stats(data)
        combined_stats.to_csv('node_stats.csv', index=False)
        print("Running stats for individual nodes")
        print("----------------------------------------------")
        single_node_stats, summary_ind = run_group_stats(data, group=['hostname','exp_command'])
        single_node_stats.to_csv('single_node_stats.csv', index=False)
        print("Comparing individual node stats with combined")
        print("----------------------------------------------")
        #compare_single_nod(combined_stats, single_node_stats)

def run_group_stats(data, group=['exp_command']):
    fixed_data = data[data['random'] == 0]
    random_data = data[data['random'] == 1]

    # Shapiro-Wilk to test for normality
    print("Running Shapiro-Wilk on fixed data")
    print("----------------------------------------------")
    shapiro_wilk_fixed, shapiro_summary_fixed = SW_test(fixed_data,"result",group,"fixed")

    print("Running Shapiro-Wilk on random data")
    print("----------------------------------------------")
    shapiro_wilk_random, shapiro_summary_random = SW_test(random_data,"result",group, "random")

    # Kruskal Wallis
    print("Running Kruskal Wallis")
    print("----------------------------------------------")
    kruskal_wallace = KW_test(data,"result", group)
    kw_summary = summarize_kw_results(kruskal_wallace)

    stats_all = shapiro_wilk_fixed.merge(shapiro_wilk_random, how='outer', on=group)
    stats_all = stats_all.merge(kruskal_wallace, how='outer', on=group)
    summary = pd.concat([shapiro_summary_fixed, shapiro_summary_random, kw_summary],
                        axis=1)
    # TODO: Add in confidence interval
    return stats_all, summary

"""##SHAPIRO WILK TEST"""
def SW_test(df, measure, group, order):
  df_cols = group + ['S-W test statistic ' + order,
                     'S-W p-value ' + order]
  shapiro_wilk = pd.DataFrame(columns=df_cols)
  shapiro_stats = pd.DataFrame(columns=['S-W Number not normal ' + order,
                                        'S-W Number normal ' + order,
                                        'Fraction not normal ' + order])
  for key, grp in df.groupby(group):
      if len(group) == 1:
          config = [key]
      else:
          config = list(key)

      shapiro_wilk.loc[len(shapiro_wilk)] = config + \
                                            [stats.shapiro(grp[measure])[0],
                                            stats.shapiro(grp[measure])[1]]

  num_not_normal = len(shapiro_wilk[shapiro_wilk["S-W p-value " + order]<0.05])
  num_normal = len(shapiro_wilk) - num_not_normal
  frac_not_normal = num_not_normal / len(shapiro_wilk)
  shapiro_stats.loc[len(shapiro_stats)] = [num_not_normal,
                                            num_normal,
                                            frac_not_normal]
  print("Number of configurations not normally distributed", num_not_normal)
  print("Number of configurations normally distributed", num_normal)
  print("Fraction of configurations not normally distributed", frac_not_normal)
  print("\n\n")

  return shapiro_wilk, shapiro_stats

def KW_test(df, measure, group):
  # Samples with fewer than this number of values will not be considered
  sample_count_thresh = 50
  kruskal_wallace = pd.DataFrame(columns = group + \
                                            ['K-W test statistic',
                                            'K-W p-value',
                                            'percent diff',
                                            'K-W effect size'])

  # Compare between fixed and random for each configuration
  for idx, grp in df.groupby(group):
    fixed_results = grp[grp.random == 0][measure].values
    fixed_results = fixed_results.astype(np.float64)
    random_results= grp[grp.random == 1][measure].values
    random_results = random_results.astype(np.float64)

    # run test and compute results
    kw_stats = stats.kruskal(fixed_results, random_results)
    p_diff = percent_difference(fixed_results, random_results)
    effect_size = effect_size_eta_squared_KW(fixed_results, random_results, kw_stats[0])

    # needed for use with group size of one or >1
    if len(group) == 1:
        config = [idx]
    else:
        config = list(idx)
    # if (len(random_sample) >= sample_count_thresh) and (len(seq_sample) >= sample_count_thresh): #WHEN SUFFICIENT DATA IS PRESENT
    kruskal_wallace.loc[len(kruskal_wallace)] = config + \
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

def get_median(df):
    try:
        return stat.median(df.values)
    except:
        return np.nan

def get_percentile(df, quant):
    try:
        return df.quantile(quant)
    except:
        return np.nan

def summarize_kw_results(kw_data):
    # calculating average percentage difference
    kw_data['abs percent diff'] = kw_data['percent diff'].apply(abs)
    avg_pd = sum(kw_data["abs percent diff"].values) / len(kw_data)
    print("Average percent difference: %f\n\n" % avg_pd)

    # Looking at whether the random or the fixed order performed better
    print("Random vs. Fixed Order Performance")
    print("----------------------------------------------")
    pos = kw_data[(kw_data['percent diff'] > 0) &
                    (kw_data['K-W p-value'] < 0.05)]['abs percent diff']
    neg = kw_data[(kw_data['percent diff'] < 0) &
                    (kw_data['K-W p-value'] < 0.05)]['abs percent diff']
    # add 10th percentile
    performance_summary = pd.DataFrame(columns=["fixed_greater_count",
                                                "fixed_Median",
                                                "fixed_10th",
                                                "fixed_90th",
                                                "random_greater_count",
                                                "random_Median",
                                                "random_10th",
                                                "random_90th"])
    performance_summary.loc[len(performance_summary)] = \
                            [len(pos),
                            get_median(pos),
                            get_percentile(pos, .1),
                            get_percentile(pos, .9),
                            len(neg),
                            get_median(neg),
                            get_percentile(neg, .1),
                            get_percentile(neg, .9)]
    print(performance_summary.to_string(index=False))
    return performance_summary


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
