#!/usr/bin/python3

#count the number of EDIHs in each country after full completion of data cleanup and validation


import pandas as pd
import numpy as np

FileInput = FileOutput = "combined_further_cleaned_keywords.xlsx"
Original_data = "export-edihs.xls"
df = pd.read_excel(FileInput, sheet_name="Sheet1")
original_df = pd.read_excel(Original_data)

if 'Country' in df.columns:
    #counting the occurences of each unique country in the "country" column

    country_counts = df["Country"].value_counts()
    country_counts_original = original_df["Country"].value_counts()
    print(country_counts)
    print(country_counts_original)

    with pd.ExcelWriter(FileOutput, engine='openpyxl', mode='a', if_sheet_exists='replace') as file:
        country_counts.to_excel(file, sheet_name="Count")
        country_counts_original.to_excel(file, sheet_name="old Count")
        print("\nSuccecfully updated country counts")

