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
        summary_ind.to_csv('summary_stats.csv', index=False)
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

def ci(s,  alpha=0.95, p=0.50, n_thresh=10):
    """
    For values in the given array s and p in [0, 1], this fuction returns
    empirical p-quantile value and its nonparametric 95% confidence interval.
    Refer to book by Boudec: https://infoscience.epfl.ch/record/146812/files/perfPublisherVersion_1.pdf,
    (Page 36 describes how nonparametric confidence intervals can be obtained for p-quantiles)
    """
    n = len(s)
    q = np.quantile(s, p)
    eta = stats.norm.ppf((1+alpha)/2.0) # 1.96 for alpha = 0.95
    lo_rank = max(int(np.floor(n * p - eta * np.sqrt(n * p * (1-p)))), 0)
    hi_rank = min(int(np.ceil(n * p + eta * np.sqrt(n * p * (1-p))) + 1), n-1)
    s_sorted = sorted(s.tolist())
    q_ci_lo = s_sorted[lo_rank]
    q_ci_hi = s_sorted[hi_rank]
    return q, q_ci_lo, q_ci_hi

"""##Function to calculate confidence of seq and random"""

def CI_seqvsran(datf,measure,alpha = 0.95,p = 0.5):
  df = pd.DataFrame(columns=["hw_type", "testname", "dvfs", "socket_num","MT","random","pth_quantile","low","high"])
  for idx,grp in datf.groupby(["hw_type", "testname", "dvfs", "socket_num","MT","random"]):
    m,lo,hi = ci(grp[measure].values, alpha=alpha, p=p)
    df.loc[len(df)] = list(idx) + [m,lo,hi]

  return df

def CI_cases(df):
  fin_df = pd.DataFrame(columns=["hw_type", "testname", "dvfs", "socket_num","MT", "Case", "Inner_diff"])
  for idx,grp in df.groupby(["hw_type", "testname", "dvfs", "socket_num","MT"]):
    rand = grp[grp["random"] == 1]
    seq = grp[grp["random"] == 0]
    rand_pq = rand["pth_quantile"].values[0]
    rand_high = rand["high"].values[0]
    rand_low = rand["low"].values[0]
    seq_pq = seq["pth_quantile"].values[0]
    seq_high = seq["high"].values[0]
    seq_low = seq["low"].values[0]

    ##Calculating the differences
    if(rand_high>seq_high):
      ch = rand_low - seq_high
      if(ch < 0): #Case 2 or Case 3
        ch = None

    else:
      ch = seq_low - rand_high
      if(ch < 0):
        ch = None



    #case 1 no overlap
    if(rand_low > seq_high or seq_low> rand_high): # make this else
      fin_df.loc[len(fin_df)] = list(idx) + ["Case 1", ch]

    #case 2 and 3 checking for overlap
    elif((seq_high >= rand_low and rand_high >= seq_high) or (rand_high >= seq_low and seq_high >= rand_high)):
      #case 2 checking if medians overlap
      if((rand_high>= seq_high and (seq_pq >= rand_low or rand_pq <= seq_high)) or (seq_high >= rand_high and (rand_pq >= seq_low or seq_pq <= rand_high))):
        fin_df.loc[len(fin_df)] = list(idx) + ["Case 2", ch]
      else: # case 3 no median overlap but overlap of CI present
        fin_df.loc[len(fin_df)] = list(idx) + ["Case 3", ch]
    else:
      fin_df.loc[len(fin_df)] = list(idx) + ["Potential error", ch]

  return fin_df

"""##Function to plot CI"""

# Plotting is similar to the code above
def draw_plots(df):
  fig, ax = plt.subplots(1, 1, figsize=(4, 3))
  n_list = []
  x_axis = []
  for i in range(0,len(df)):

      ax.errorbar(i, df["pth_quantile"].tolist()[i], yerr=[np.array([df["pth_quantile"].tolist()[i]-df["low"].tolist()[i]]),
                  np.array([df["high"].tolist()[0]-df["pth_quantile"].tolist()[0]])], \
                  c="orange", fmt='o')
      x_axis.append(i)

      if(((i)%2) != 0):
        print(df["hw_type"].values[i], df["testname"].values[i],df["dvfs"].values[i], df["socket_num"].values[i],df["MT"].values[i])
        plt.xticks(x_axis, ["fixed", "random"])
        plt.show()
        x_axis = []
        if(i != len(df)-1):
          fig, ax = plt.subplots(1, 1, figsize=(4, 3))

"""##Function to plot the cases split histogram"""

def CI_histo(data):
  fig, (ax) = plt.subplots(1, 1, figsize=(6,4))
  ax.bar(x = [1,3,5], height=data, tick_label= ["case1", "case2","case3"])
  ax.set_title("Histogram of the split between the cases")
  ax.set_xlabel("Case type")
  ax.set_ylabel("Number of configuration of the case type")

# cpu_ci_df = CI_seqvsran(cpu_with_random,"exec_time")
# display(cpu_ci_df)
#
# cpu_ci = CI_cases(cpu_ci_df)
#
# cpu_ci["Case"].value_counts()
#
# draw_plots(cpu_ci_df.head(20)) # to get the plots for the different cases we simply need to try different rows of mem_ci_diff and plot them
#
# counts = list(cpu_ci["Case"].value_counts())
# CI_histo(counts)

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
