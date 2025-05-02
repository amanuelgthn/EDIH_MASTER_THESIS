#!/usr/bin/env python3


import pandas as pd

df = pd.read_excel('export-edihs.xls', index_col=0)
#cleaning the dataset if it's value for either of the three columns are empty
df_cleaner = df.dropna(subset=['Formatted sectors', 'Formatted services', 'Formatted technologies'], how='any')
all_data = len(df) - 1 

df_cleaner.to_excel("trial.xlsx", sheet_name="First")

#data to count number of existing qualifying EDIHs after precleanup of data
data = {
    'country': []
}

country_counts  = df_cleaner['Country'].value_counts().to_dict()
print(type(country_counts))
print(country_counts)
qualified_data = sum(country_counts.values())
data_coverage = (qualified_data / all_data) * 100
print("the sum of all available EDIHs after cleanup is {} with a data coverage of {:.2f}% ".format(qualified_data, data_coverage))

print(df)
