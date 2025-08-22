#!/usr/bin/python3

import pandas as pd
import numpy as np

df = pd.read_excel("preCleaned.xlsx", sheet_name='Cleaned_FULL')
print(df)
newdf = df.copy()
columns_to_check = ['Formatted sectors', 'Formatted services', 'Formatted technologies']


print("Number of rows before dropping: {}".format(len(newdf)))

df_cleaned_sheet = newdf.replace('', np.nan).dropna(subset=columns_to_check, how='any')

print(df_cleaned_sheet)
print("/n")
print(len(df_cleaned_sheet), len(newdf))

to_be_merged = pd.read_excel("Scraped.xlsx")

combined = pd.concat([df_cleaned_sheet, to_be_merged])
print(combined)
combined.to_excel("combined.xlsx")