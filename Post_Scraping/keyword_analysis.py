#!/usr/bin/python3

import pandas as pd
import numpy as np
import re
from collections import Counter

# --- Configuration ---
INPUT_EXCEL_FILE = "combined_further_cleaned_keywords.xlsx"
INPUT_SHEET_NAME = "Sheet1" # Adjust this if your sheet has a different name
# Output will be written to the same file
OUTPUT_EXCEL_FILE = INPUT_EXCEL_FILE # <<< KEY CHANGE: Output to the same file
COLUMNS_TO_ANALYZE = ['Formatted sectors', 'Formatted services', 'Formatted technologies']

# --- Function to clean individual keyword entries within a cell ---
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

# --- Function to extract and count keywords from a cleaned column ---
def extract_and_count_keywords(dataframe, column_name):
    """
    Extracts keywords from a specified column (assumed to be already cleaned),
    and counts their occurrences.
    """
    all_keywords = []
    for entry in dataframe[column_name]:
        if entry: # Only process non-empty strings
            # Split by comma and extend the list
            all_keywords.extend([k.strip() for k in entry.split(',') if k.strip()])

    # Count occurrences
    keyword_counts = Counter(all_keywords)
    return keyword_counts

# --- Main Script Execution ---
if __name__ == "__main__":
    print(f"Loading data from '{INPUT_EXCEL_FILE}' sheet '{INPUT_SHEET_NAME}'...")
    try:
        df = pd.read_excel(INPUT_EXCEL_FILE, sheet_name=INPUT_SHEET_NAME)
    except FileNotFoundError:
        print(f"Error: The file '{INPUT_EXCEL_FILE}' was not found.")
        print("Please ensure the file is in the same directory as the script, or provide the full path.")
        exit()
    except KeyError:
        print(f"Error: The sheet '{INPUT_SHEET_NAME}' was not found in '{INPUT_EXCEL_FILE}'.")
        print("Please check the sheet name and update 'INPUT_SHEET_NAME' variable.")
        exit()

    # Create a deep copy to work with, protecting the original df
    df_working = df.copy()

    # --- Step 1: Clean the relevant columns in the working DataFrame ---
    print("Cleaning keyword columns (removing numbers/special characters, converting to lowercase)...")
    for col in COLUMNS_TO_ANALYZE:
        # Ensure column exists before processing
        if col in df_working.columns:
            df_working[col] = df_working[col].astype(str).replace('nan', '')
            df_working[col] = df_working[col].apply(clean_keyword_entry)
        else:
            print(f"Warning: Column '{col}' not found in the DataFrame. Skipping cleaning for this column.")

    # --- Step 2: Perform analysis and prepare DataFrames for each category ---
    analysis_results = {}

    for col_name in COLUMNS_TO_ANALYZE:
        if col_name in df_working.columns:
            print(f"\nAnalyzing '{col_name}'...")
            counts = extract_and_count_keywords(df_working, col_name)

            # Convert Counter to DataFrame
            df_counts = pd.DataFrame(counts.items(), columns=['Keyword', 'Count'])

            # Sort by count in descending order
            df_counts = df_counts.sort_values(by='Count', ascending=False).reset_index(drop=True)

            # Calculate percentage
            total_keywords = df_counts['Count'].sum()
            if total_keywords > 0:
                df_counts['Percentage'] = (df_counts['Count'] / total_keywords * 100).round(2)
            else:
                df_counts['Percentage'] = 0.00 # Handle case where no keywords are found

            analysis_results[col_name] = df_counts
            print(f"Analysis complete for '{col_name}'. Top 5 keywords:")
            print(df_counts.head())
        else:
            print(f"Skipping analysis for '{col_name}' as it was not found in the DataFrame.")


    # --- Step 3: Write results to new sheets in the same Excel file ---
    # Use mode='a' for append mode to add sheets without overwriting existing ones.
    print(f"\nWriting analysis results to '{OUTPUT_EXCEL_FILE}'...")
    try:
        with pd.ExcelWriter(OUTPUT_EXCEL_FILE, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            # Note: For 'openpyxl' engine with mode='a', if_sheet_exists='replace' will overwrite if sheet exists,
            # otherwise it will create. If you want to strictly append and never replace, you'd need more complex logic
            # to check if sheet exists and skip if it does.
            # 'replace' is generally safer for analysis outputs as you often want the latest run.

            for col_name, df_result in analysis_results.items():
                # Determine sheet name based on original column name
                sheet_name = col_name.replace('Formatted ', '').replace(' ', '_') + '_Analysis'
                df_result.to_excel(writer, sheet_name=sheet_name, index=False)
                print(f"  - Wrote '{col_name}' analysis to sheet '{sheet_name}'")

        print(f"\nSuccessfully updated '{OUTPUT_EXCEL_FILE}' with keyword analysis sheets.")

    except Exception as e:
        print(f"An error occurred while writing to the Excel file: {e}")
        print("This might happen if the Excel file is open. Please close it and try again.")
        print("Also ensure the 'openpyxl' engine is installed: pip install openpyxl")