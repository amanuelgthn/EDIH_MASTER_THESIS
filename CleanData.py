#!/usr/bin/env python3

from typing import Tuple
import pandas as pd
import numpy as np

def cleanData(
        df: pd.DataFrame,
        subset_cols: list[str] = None,
        thresh: int = 3,
        website_col: str = 'Website',
        target_cols: list[str] = ['Formatted services',
                                  'Formatted sectors',
                                  'Formatted technologies']) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Cleans the DataFrame by dropping rows with fewer than `thresh` non-null values
    among the specified `subset_cols`, then identifies rows eligible for scraping.

    Parameters:
    - df: original DataFrame.
    - subset_cols: list of columns to enforce non-null threshold (default: target_cols + [website_col]).
    - thresh: minimum number of non-null columns required to keep a row.
    - website_col: name of the column containing URLs.
    - target_cols: list of formatted columns to check for missing values.

    Returns:
    - df_cleaner: DataFrame after dropna with threshold applied.
    - df_to_scrape: subset of df_cleaner where any target_cols are missing and website_col is present.
    - missing_info: boolean DataFrame indicating which target_cols are missing in df_to_scrape.
    """

    #setting default susbet column sample could be [Formatted sectors','Formatted sectors','Formatted technologies, 'Websites']
    if subset_cols is None:
        subset_cols = target_cols + [website_col]
    print(subset_cols)

    df.replace('', np.nan, inplace=True)
    #first step cleanup; dropping those which doesn't have at least three of the mentioned columns
    df_cleaner = df.dropna(subset=subset_cols, thresh=thresh)

    return df_cleaner


def data_to_scrape(df_cleaned: pd.DataFrame, website_col: str = 'Website',
                   subset_cols: list[str] = None,
                   target_cols: list[str] = ['Formatted services',
                                            'Formatted sectors',
                                             'Formatted technologies'] )-> Tuple[pd.DataFrame,pd.DataFrame]:
    
    if subset_cols is None:
        subset_cols = target_cols + [website_col]
    #Second step; identify row missing data but with a valid website
    needs_scraping_mask = (
        df_cleaned[website_col].notna()
        & df_cleaned[target_cols].isna().any(axis=1)            # has a valid website
    )

    df_to_scrape = df_cleaned.loc[needs_scraping_mask].copy()

    # Step 3: Record which fields are missing
    missing_info = df_to_scrape[target_cols].isna()

    return df_to_scrape, missing_info