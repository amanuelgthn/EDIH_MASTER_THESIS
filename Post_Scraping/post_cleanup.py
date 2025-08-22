#!/usr/bin/python3

import pandas as pd
import numpy as np
import re

#loading the excel file

try:
    df = pd.read_excel("combined_further.xlsx")
except:
    print("Either file not found or keyerror")
print(df)

# Create a deep copy to work with, protecting your original DataFrame
df_cleaned_keywords = df.copy()

# Ensure the relevant columns are treated as strings and handle NaN
# Replace NaN with empty strings so string operations don't fail
df_cleaned_keywords['Formatted sectors'] = df_cleaned_keywords['Formatted sectors'].astype(str).replace('nan', '')
df_cleaned_keywords['Formatted services'] = df_cleaned_keywords['Formatted services'].astype(str).replace('nan', '')
df_cleaned_keywords['Formatted technologies'] = df_cleaned_keywords['Formatted technologies'].astype(str).replace('nan', '')

def clean_keyword_entry(entry_string):
    """
    Cleans a single comma-separated keyword string:
    - Removes numbers and special characters (except spaces) from individual keywords.
    - Converts keywords to lowercase.
    - Replaces multiple spaces with single spaces.
    - Joins them back with a comma and space.
    """
    if not entry_string: # Handle empty strings
        return ''

    individual_keywords = entry_string.split(',')
    cleaned_parts = []
    for keyword in individual_keywords:
        # Remove numbers and special characters, keeping only letters and spaces
        cleaned_part = re.sub(r'[^a-zA-Z\s]', '', keyword).strip()
        # Replace multiple spaces with a single space and strip again
        cleaned_part = re.sub(r'\s+', ' ', cleaned_part).strip()
        if cleaned_part: # Only add non-empty parts
            cleaned_parts.append(cleaned_part.lower()) # Convert to lowercase

    return ', '.join(cleaned_parts)

# Apply the cleaning function to each of the specified columns
print("--- Cleaning keyword columns ---")
df_cleaned_keywords['Formatted sectors'] = df_cleaned_keywords['Formatted sectors'].apply(clean_keyword_entry)
df_cleaned_keywords['Formatted services'] = df_cleaned_keywords['Formatted services'].apply(clean_keyword_entry)
df_cleaned_keywords['Formatted technologies'] = df_cleaned_keywords['Formatted technologies'].apply(clean_keyword_entry)

print("\n--- Original DataFrame (first 5 rows of relevant columns) ---")
print(df[['Formatted sectors', 'Formatted services', 'Formatted technologies']].head())

print("\n--- DataFrame with Cleaned Keywords (first 5 rows of relevant columns) ---")
print(df_cleaned_keywords[['Formatted sectors', 'Formatted services', 'Formatted technologies']].head())

# Optional: Save the updated DataFrame to a new Excel file
df_cleaned_keywords.to_excel("combined_further_cleaned_keywords.xlsx", index=False)
# print("\nCleaned DataFrame saved to 'combined_further_cleaned_keywords.xlsx'")