import os
import pandas as pd
from matplotlib import pyplot as plt
import numpy as np
import statistics as stat
import scipy.stats as stats
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='Description of supported command-line arguments:')
    parser.add_argument('-f','--file', type=str, default='',
                        help='CSV file to obtain cumulative data')

    args = parser.parse_args()

    if args.file == '':
        LOG.critical('Invalid Arguments: Please provide \'-f filename\'')
        sys.exit(1)

    return args

def get_median(df):
    try:
        return stat.median(df.values)
    except:
        return np.nan

"""
For values in the given array s and p in [0, 1], this fuction returns
empirical p-quantile value and its nonparametric 95% confidence interval.
Refer to book by Boudec:
https://infoscience.epfl.ch/record/146812/files/perfPublisherVersion_1.pdf,
(Page 36 describes how nonparametric confidence intervals can be obtained
for p-quantiles)
"""
def get_ci(s,  alpha=0.95, p=0.5, n_thresh=10):
    n = len(s)
    q = np.quantile(s, p)
    eta = stats.norm.ppf((1+alpha)/2.0) # 1.96 for alpha = 0.95
    lo_rank = max(int(np.floor(n * p - eta * np.sqrt(n * p * (1-p)))), 0)
    hi_rank = min(int(np.ceil(n * p + eta * np.sqrt(n * p * (1-p))) + 1), n-1)
    s_sorted = sorted(s.tolist())
    q_ci_lo = s_sorted[lo_rank]
    q_ci_hi = s_sorted[hi_rank]
    return q_ci_hi, q_ci_lo

def aggregate_results(df):
    agg_stats = pd.DataFrame(columns = ['exp_command',
                                        'order_type',
                                        'run_num',
                                        'result',
                                        'median_cmltv',
                                        'ci_hi_cmltv',
                                        'ci_lo_cmltv'])

    for idx, group in df.groupby(['exp_command', 'order_type']):
        for i in range(0,480,2):
            if idx[1] == "random":
                i = i + 1
            result = group[group['run_num'] == i]['result'].values[0]
            agg_result = group[group['run_num'] <= i]['result']
            med = get_median(agg_result)
            ci_hi,ci_lo = get_ci(agg_result)
            agg_stats.loc[len(agg_stats)] = list(idx) + [i, result, med, ci_hi, ci_lo]

    return agg_stats

# TODO: Fix axes, add concise name for fig name
def plot(df):
    for idx, group in df.groupby(['exp_command']):
        f = group[group['order_type'] == 'fixed']
        r = group[group['order_type'] == 'random']

        plt.figure(figsize=(25,15))
        plt.plot(f['run_num'], f['median_cmltv'], label='fixed')
        plt.plot(r['run_num'], r['median_cmltv'], label='random')
        plt.fill_between(f['run_num'], f['ci_lo_cmltv'], f['ci_hi_cmltv'],
                         color='b', alpha=.1)
        plt.fill_between(r['run_num'], r['ci_lo_cmltv'], r['ci_hi_cmltv'],
                         color='r', alpha=.1)
        plt.xticks(list(range(0,480,20)))
        plt.legend()
        sv = str(idx) + '_112921.pdf'
        #plt.show()
        plt.savefig(sv)

def main():
    args = parse_args()
    s = args.file
    df = pd.read_csv(s)
    agg_df = aggregate_results(df)

    filename = s[:-4]
    agg_df.to_csv(filename + '_agg.csv', index=False)


if __name__ == "__main__":
    main()
