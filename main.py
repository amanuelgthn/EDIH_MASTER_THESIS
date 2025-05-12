#!/usr/bin/env python3


import pandas as pd
# from openpyxl import load_workbook


# # Generating workbook and writer engine
# excel_workbook = load_workbook("data_before.xlsx")
# writer = pd.ExcelWriter("data_before.xlsx", engine='openpyxl')
# writer.book = excel_workbook
df = pd.read_excel('export-edihs.xls', index_col=0)
#cleaning the dataset if it's value for either of the three columns are empty
df_cleaner = df.dropna(subset=['Formatted sectors', 'Formatted services', 'Formatted technologies', 'Description (indexed field)'], thresh=2)
all_data = len(df)

data_row = {
    'country'
}

data_before = df['Country'].value_counts().to_dict()
print(data_before)
data_before_df = pd.DataFrame.from_dict(data_before, orient='index')

top = 20
print("\n\n\n\n")
word_counts_services = (
        df_cleaner['Formatted services']
            .dropna()
            .str.lower()
            .str.rstrip(',')
            .str.split(r',\s*')
            .explode()
            .str.strip()
            .replace('', pd.NA)
            .dropna()
            .value_counts()
            .head(top)
)
print("The most common occuring key words on Formatted serviecs are the following \n{}".format(word_counts_services))
print("\n\n\n\n")
word_counts_technologies = (
        df_cleaner['Formatted technologies']
            .dropna()
            .str.lower()
            .str.rstrip(',')
            .str.split(r',\s*')
            .explode()
            .str.strip()
            .replace('', pd.NA)
            .dropna()
            .value_counts()
            .head(top)
)
print("The most common occuring key words on Formatted technologies are the following \n{}".format(word_counts_technologies))
print("\n\n\n\n")
word_counts_sectors = (
        df_cleaner['Formatted sectors']
            .dropna()
            .str.lower()
            .str.rstrip(',')
            .str.split(r',\s*')
            .explode()
            .str.strip()
            .replace('', pd.NA)
            .dropna()
            .value_counts()
            .head(top)
)
print("The most common occuring key words on Formatted sectors are the following \n{}".format(word_counts_sectors))
print("\n\n\n\n")
# data_before_df.to_excel(writer,  sheet_name="Original")
# df_cleaner.to_excel("trial.xlsx", sheet_name="First")
# df_cleaner.to_excel(writer, sheet_name="Cleaned_up")


df_cleaner_unique = df.drop_duplicates()
unique_length = len(df_cleaner_unique)

#data to count number of existing qualifying EDIHs after precleanup of data
data = {
    'country': []
}


country_counts  = df_cleaner['Country'].value_counts().to_dict()
missing = data_before.keys() - country_counts.keys()
print(missing)
with pd.ExcelWriter("trial.xlsx", engine="openpyxl") as writer:
    data_before_df.to_excel(writer, sheet_name="before")
    country_counts_df = pd.DataFrame.from_dict(country_counts, orient="index")
    country_counts_df.to_excel(writer, sheet_name="cleaned")
    df_cleaner.to_excel(writer, sheet_name="Cleaned_FULL")
print(type(country_counts))
print(country_counts)
qualified_data = sum(country_counts.values())

data_coverage = (qualified_data / all_data) * 100

print("\nThe sum of all available EDIHs after cleanup is {} with a data coverage of {:.2f}% ".format(qualified_data, data_coverage))
print("Thhe length of the data before cleanup is {}".format(all_data))
print("The length after dropping duplicates is {}".format(unique_length))

print(df)
