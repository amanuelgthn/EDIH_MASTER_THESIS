#!/usr/bin/env python3


from typing import Tuple
from CleanData import prepare_scrape_df, data_to_scrape
import pandas as pd
import CategoryScraper


# from openpyxl import load_workbook


def get_word_count(Formatted__Category: str, dataframe: pd.DataFrame)-> Tuple[str, pd.DataFrame]:
    word_counts = ''
    pattern = '\s*-\s*\d+\b'
    word_counts = (
        dataframe[Formatted__Category]
            .dropna()
            .str.lower()
            .str.replace(r'\s*-\s*\d+\b', '', regex=True)
            .str.split(r',\s*')
            .explode()
            .str.strip()
            .value_counts()
    )
    word_counts_df = (
            word_counts
                .reset_index()
                .rename(columns={'index': 'Category', 0: 'Count'})
    )
    words = word_counts.index.tolist()
    return words, word_counts, word_counts_df
# # Generating workbook and writer engine
# excel_workbook = load_workbook("data_before.xlsx")
# writer = pd.ExcelWriter("data_before.xlsx", engine='openpyxl')
# writer.book = excel_workbook
df = pd.read_excel('export-edihs.xls', index_col=0)
#cleaning the dataset if it's value for either of the three columns are empty
df['Website'] = (
    df['Website']
      .fillna('')
      .astype(str)  # in case you have NaNs
      .str.replace(r'(?i)^website$', '', regex=True)
)

df_cleaner = prepare_scrape_df(df)

all_data = len(df)

data_row = {
    'country'
}

data_before = df['Country'].value_counts().to_dict()
print(data_before)
data_before_df = pd.DataFrame.from_dict(data_before, orient='index')

top = 20
print("\n\n\n\n")
keywords_list_services, word_counts_services,word_counts_services_df  = get_word_count('Formatted services', df_cleaner)
       
print("The most common occuring key words on Formatted serviecs are the following \n{}".format(word_counts_services))
print("\n\n\n\n")
keywords_list_technologies, word_counts_technologies, word_counts_technologies_df = get_word_count('Formatted technologies', df_cleaner)
print("The most common occuring key words on Formatted technologies are the following \n{}".format(word_counts_technologies))
print("\n\n\n\n")
keywords_list_sectors, word_counts_sectors, word_counts_sectors_df = get_word_count('Formatted sectors', df_cleaner)
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
for item in missing:
    condition = (
        (df['Country'] == item)
        & df['Website'].notna()
        &(
            df['Formatted sectors'].fillna('').str.strip().ne('')
            | df['Formatted services'].fillna('').str.strip().ne('')
            | df['Formatted technologies'].fillna('').str.strip().ne('')
        )
    )
    add_row = df.loc[condition]

df_cleaner = pd.concat([df_cleaner, add_row], ignore_index=True)

df_to_scrape, missing_info = data_to_scrape(df_cleaner)
country_counts  = df_cleaner['Country'].value_counts().to_dict()

scraper = CategoryScraper.CategoryScraper(
    df = df_to_scrape,
    site_col =  'Website',
    sector_keywords =  keywords_list_sectors,
    service_keywords =  keywords_list_services,
    tech_keywords =  keywords_list_technologies

)

df_filled = scraper.fill_missing()
with pd.ExcelWriter("trial_Scraped.xlsx", engine="openpyxl") as writer:
    df_filled.to_excel(writer, sheet_name="Data_scrapped")
# with pd.ExcelWriter("trial.xlsx", engine="openpyxl") as writer:
#     data_before_df.to_excel(writer, sheet_name="before")
#     country_counts_df = pd.DataFrame.from_dict(country_counts, orient="index")
#     country_counts_df.to_excel(writer, sheet_name="cleaned")
#     df_cleaner.to_excel(writer, sheet_name="Cleaned_FULL")
#     word_counts_services_df.to_excel(writer, sheet_name='services')
#     word_counts_technologies_df.to_excel(writer, sheet_name='technologies')
#     word_counts_sectors_df.to_excel(writer, sheet_name='sectors')~
#     df_to_scrape.to_excel(writer, sheet_name='data required to be scrapped')
#     missing_info.to_excel(writer, sheet_name='missing info')
print(type(country_counts))
print(country_counts)
qualified_data = sum(country_counts.values())

data_coverage = (qualified_data / all_data) * 100

print("\nThe sum of all available EDIHs after cleanup is {} with a data coverage of {:.2f}% ".format(qualified_data, data_coverage))
print("Thhe length of the data before cleanup is {}".format(all_data))
print("The length after dropping duplicates is {}".format(unique_length))

print(df)
