import sys
import numpy as np
import datetime as dt
import pandas as pd
import glob
import datetime
import statistics as stat
import scipy.stats as stats
import itertools
from logger import configure_logging

LOG = configure_logging(name="toolstats", filter = True, debug = True, \
                        to_console = True, filename = "mainlogfile.log")

def process_data(data):
    # Remove failures
    fixed_failures = data[(data['completion_status'] == 'Failure') &\
                         (data['order_type'] == 'fixed')]
    # Drop all fixed runs with failed experiments
    data = data[~(data['run_uuid'].isin(fixed_failures['run_uuid']))]
    # Drop all experiments failed in random runs
    data = data[~(data['completion_status'] == 'Failure')]

    return data

def run_stats(data, results_dir, timestamp):
    # Process data, removing failures
    data = process_data(data)
    # Record single or multinode and split data by order type
    n_nodes = len(data['hostname'].unique())

    if n_nodes == 1:
        LOG.info("Running stats for single node")
        LOG.info("----------------------------------------------")
        node_stats, summary = run_group_stats(data)
        node_stats.to_csv(results_dir + '/' + timestamp + '_node_stats.csv', index=False)
        summary.to_csv(results_dir + '/' + timestamp + '_stats_summary.csv', index=False)
    else:
        # run stats for all
        LOG.info("Running stats for combined nodes")
        LOG.info("----------------------------------------------")
        combined_stats, summary_all = run_group_stats(data)
        combined_stats.to_csv(results_dir + '/' + timestamp + '_combined_node_stats.csv', index=False)
        combined_stats.to_csv(results_dir + '/' + timestamp + '_combined_stats_summary.csv', index=False)
        LOG.info("Running stats for individual nodes")
        LOG.info("----------------------------------------------")
        single_node_stats, summary_ind = run_group_stats(data, group=['hostname','exp_command'])
        single_node_stats.to_csv(results_dir + '/' + timestamp + '_indv_node_stats.csv', index=False)
        summary_ind.to_csv(results_dir + '/' + timestamp + '_indv_stats_summary.csv', index=False)
        LOG.info("Comparing individual node stats with combined")
        LOG.info("----------------------------------------------")
        compared_stats = compare_nodes(combined_stats, single_node_stats)
        compared_stats.to_csv(results_dir + '/' + timestamp + 'compared_stats.csv', index=False)

def run_group_stats(data, group=['exp_command']):
    fixed_data = data[data['order_type'] == 'fixed']
    random_data = data[data['order_type'] == 'random']

    # Shapiro-Wilk to test for normality
    LOG.info("Running Shapiro-Wilk on fixed data")
    LOG.info("----------------------------------------------")
    shapiro_wilk_fixed, shapiro_summary_fixed = SW_test(fixed_data,"result",group,"fixed")

    LOG.info("Running Shapiro-Wilk on random data")
    LOG.info("----------------------------------------------")
    shapiro_wilk_random, shapiro_summary_random = SW_test(random_data,"result",group, "random")

    # Kruskal Wallis
    LOG.info("Running Kruskal Wallis")
    LOG.info("----------------------------------------------")
    kruskal_wallace = KW_test(data,"result", group)
    kw_summary = summarize_kw_results(kruskal_wallace)

    # CI testing
    LOG.info("Comparing Confidence Intervals")
    LOG.info("----------------------------------------------")
    conf_intervals = CI_fixed_vs_random(data, "result", group)

    stats_all = shapiro_wilk_fixed.merge(shapiro_wilk_random, how='outer', on=group)
    stats_all = stats_all.merge(kruskal_wallace, how='outer', on=group)
    stats_all = stats_all.merge(conf_intervals, how='outer', on=group)
    summary = pd.concat([shapiro_summary_fixed, shapiro_summary_random, kw_summary],
                        axis=1)
    stats_all = stats_all.sort_values(by=['coeff_of_variation'], ascending=False)
    idx = len(group)
    # Shift high level stats to front
    stats_all.insert(idx, 'coeff_of_variation', stats_all.pop('coeff_of_variation'))
    stats_all.insert(idx+1, 'KW_dist_type', stats_all.pop('KW_dist_type'))
    stats_all.insert(idx+2, 'Normal_fixed', stats_all.pop('Normal_fixed'))
    stats_all.insert(idx+3, 'Normal_random', stats_all.pop('Normal_random'))

    return stats_all, summary

"""##SHAPIRO WILK TEST"""
def SW_test(df, measure, group, order):
    df_cols = group + ['SW_test_stat_' + order,
                     'SW_p-value_' + order,
                     'Normal_' + order]
    shapiro_wilk = pd.DataFrame(columns=df_cols)
    shapiro_stats = pd.DataFrame(columns=['SW_num_not_normal_' + order,
                                        'SW_number_normal_' + order,
                                        'Fraction_not_normal_' + order])
    for key, grp in df.groupby(group):
        if len(group) == 1:
            config = [key]
        else:
            config = list(key)
        sw = stats.shapiro(grp[measure])
        normal = True if sw[1] > 0.05 else False
        shapiro_wilk.loc[len(shapiro_wilk)] = config + \
                                            [sw[0],
                                            sw[1],
                                            normal]

    num_not_normal = len(shapiro_wilk[shapiro_wilk["SW_p-value_" + order]<0.05])
    num_normal = len(shapiro_wilk) - num_not_normal
    frac_not_normal = num_not_normal / len(shapiro_wilk)
    shapiro_stats.loc[len(shapiro_stats)] = [num_not_normal,
                                            num_normal,
                                            frac_not_normal]
    LOG.info("Number of configurations not normally distributed " + str(num_not_normal))
    LOG.info("Number of configurations normally distributed " + str(num_normal))
    LOG.info("Fraction of configurations not normally distributed " + str(frac_not_normal))

    return shapiro_wilk, shapiro_stats

def KW_test(df, measure, group):
    # Samples with fewer than this number of values will not be considered
    sample_count_thresh = 50
    kruskal_wallace = pd.DataFrame(columns = group + \
                                            ['KW_dist_type',
                                            'coeff_of_variation',
                                            'KW_test_stat',
                                            'KW_p-value',
                                            'percent_diff',
                                            'KW_effect_size'])

    # Compare between fixed and random for each configuration
    for idx, grp in df.groupby(group):
        fixed_results = grp[grp.order_type == 'fixed'][measure].values
        fixed_results = fixed_results.astype(np.float64)
        random_results= grp[grp.order_type == 'random'][measure].values
        random_results = random_results.astype(np.float64)

        # run test and compute results
        coef_of_var = round(stats.variation(grp[measure].values), 3)
        kw_stats = stats.kruskal(fixed_results, random_results)
        p_diff = percent_difference(fixed_results, random_results)
        effect_size = effect_size_eta_squared_KW(fixed_results, random_results, kw_stats[0])
        kw_dist = get_distribution(kw_stats[1])
        # needed for use with group size of one or >1
        if len(group) == 1:
            config = [idx]
        else:
            config = list(idx)
        #WHEN SUFFICIENT DATA IS PRESENT
        # if (len(random_sample) >= sample_count_thresh) and (len(seq_sample) >= sample_count_thresh):
        kruskal_wallace.loc[len(kruskal_wallace)] = config + \
                                                [kw_dist,
                                                coef_of_var,
                                                kw_stats[0],
                                                kw_stats[1],
                                                p_diff,
                                                effect_size]

    return kruskal_wallace

def get_distribution(p_val):
    return 'same' if p_val > 0.05 else 'different'

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
    kw_data['abs_percent_diff'] = kw_data['percent_diff'].apply(abs)
    avg_pd = sum(kw_data["abs_percent_diff"].values) / len(kw_data)
    LOG.info("Average percent difference: " + str(avg_pd))

    # Looking at whether the random or the fixed order performed better
    LOG.info("Random vs. Fixed Order Performance")
    LOG.info("----------------------------------------------")
    pos = kw_data[(kw_data['percent_diff'] > 0) &
                    (kw_data['KW_p-value'] < 0.05)]['abs_percent_diff']
    neg = kw_data[(kw_data['percent_diff'] < 0) &
                    (kw_data['KW_p-value'] < 0.05)]['abs_percent_diff']
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
    LOG.info(performance_summary.to_string(index=False))
    return performance_summary


def CI_fixed_vs_random(data, measure, group, alpha = 0.95, p = 0.5):
    df = pd.DataFrame(columns=group +["fixed_pth_quantile",
                                      "fixed_ci_low",
                                      "fixed_ci_high",
                                      "random_pth_quantile",
                                      "random_ci_low",
                                      "random_ci_high",
                                      "ci_case",
                                      "inner_diff"])

    for idx,grp in data.groupby(group):
        fixed_results = grp[grp.order_type == 'fixed'][measure].values
        fixed_results = fixed_results.astype(np.float64)
        random_results= grp[grp.order_type == 'random'][measure].values
        random_results = random_results.astype(np.float64)

        f_m,f_lo,f_hi = get_ci(fixed_results, alpha=alpha, p=p)
        r_m,r_lo,r_hi = get_ci(random_results, alpha=alpha, p=p)

        # needed for use with group size of one or >1
        if len(group) == 1:
            config = [idx]
        else:
            config = list(idx)

        # Check CI overlap cases
        # Calculating the inner difference
        if(r_hi>f_hi):
            inner_diff = r_lo - f_hi
            if inner_diff > 0:
                case = 1
            elif (f_m >= r_lo) or (r_m <= f_hi):
                case = 2
                inner_diff = None
            else:
                case = 3
                inner_diff = None
        else:
            inner_diff = f_lo - r_hi
            if inner_diff > 0:
                case = 1
            elif (r_m > f_lo) or (f_m < r_hi):
                case = 2
                inner_diff = None
            else:
                case = 3
                inner_diff = None

        df.loc[len(df)] = config + [f_m,f_lo,f_hi,r_m,r_lo,r_hi,case, inner_diff]

    return df

def get_ci(s,  alpha=0.95, p=0.5, n_thresh=10):
    """
    For values in the given array s and p in [0, 1], this fuction returns
    empirical p-quantile value and its nonparametric 95% confidence interval.
    Refer to book by Boudec:
    https://infoscience.epfl.ch/record/146812/files/perfPublisherVersion_1.pdf,
    (Page 36 describes how nonparametric confidence intervals can be obtained
    for p-quantiles)
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

def compare_nodes(combined_stats, single_stats):
    compared_stats = combined_stats[['exp_command']].copy()
    compared_stats['COV_all'] = combined_stats['coeff_of_variation']
    compared_stats['KW_dist_type_all'] = combined_stats['KW_dist_type']
    compared_stats['CI_case_all'] = combined_stats['ci_case']
    dist_overview = []

    # Run through each node and generate stats on distribution by experiment
    for idx, group in single_stats.groupby(['hostname']):
        ss = group[['exp_command']].copy()
        ss['KW_dist_type_' + idx] = group['KW_dist_type']
        ss['CI_case_' + idx] = group['ci_case']
        ss['COV_' + idx] = group['coeff_of_variation']
        compared_stats = compared_stats.merge(ss, how='outer', on='exp_command')
        overview = compared_stats['KW_dist_type_' + idx].tolist()
        overview = list(map((lambda x: x[0]), overview))
        dist_overview.append(overview)

    # Transpose overview list and add as column
    dist_overview = list(map(list, itertools.zip_longest(*dist_overview, fillvalue=None)))
    compared_stats.insert(loc=4, column='KW_dist_overview', value=dist_overview)
    compared_stats['KW_dist_overview'] = compared_stats['KW_dist_overview'].apply(convert_list)
    return compared_stats

def convert_list(l):
    return '-'.join(l)

def main():
    df = pd.read_csv('examples/test_data.csv')
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H:%M:%S")
    run_stats(df, 'examples', timestamp)

if __name__ == "__main__":
    main()
