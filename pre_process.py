import pandas as pd

# Change to whatever *_all_exp_results.csv you want to fix
df = pd.read_csv('20211017_14:40:18_results/20211017_14:40:18_all_exp_results.csv')

def to_float_list(s):
    list_ = [float(x) for x in s.split(',')]
    if len(list_) == 1:
        return list_[0]
    else:
        return list_

df['result'] = df['result'].apply(to_float_list)

#print(len(df))
df_mem = df[df['exp_number'] == 0]
df = df[df['exp_number'] != 0]
#print(len(df_mem))
#print(len(df))
tests = ['copy_omp','scale_omp','add_omp', 'triad_omp']
for index, row in df_mem.iterrows():
    results = row['result']
    id = row['exp_command']

    for i,r in enumerate(results):
        temp = row.copy()
        temp['result'] = r
        temp['exp_command'] = id + ' -- ' + tests[i]
        df = df.append(temp)

#print(len(df))
df.to_csv('20211017_14:40:18_results/20211017_14:40:18_all_exp_results_clean.csv')
