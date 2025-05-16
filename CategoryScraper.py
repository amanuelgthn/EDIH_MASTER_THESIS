#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict
import pandas as pd


class CategoryScraper:
    """
    Encapsulates logic to fill missing Formatted sectors, services,
    and technologies columns by scraping hub websites for known keywords.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        site_col: str,
        sector_keywords: List[str],
        service_keywords: List[str],
        tech_keywords: List[str],
    ):
        self.df = df.copy()
        self.site_col = site_col
        # mapping from DataFrame column → list of keywords to look for
        self.mapping: Dict[str, List[str]] = {
            'Formatted sectors': sector_keywords,
            'Formatted services': service_keywords,
            'Formatted technologies': tech_keywords,
        }

    def scrape_by_keywords(self, base_url: str, keywords: List[str]) -> List[str]:
        """
        1) Fetch base_url, parse links; if any <a> text or href matches a keyword slug,
           follow that link, else stay on base_url.
        2) Scan the chosen page for all keywords and return those found.
        """
        try:
            resp = requests.get(base_url, timeout=8)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
        except Exception:
            return []

        # try to find a dedicated subpage for any keyword
        subpage_url = None
        for a in soup.select('a[href]'):
            href = a['href']
            text = a.get_text(" ", strip=True).lower()
            for kw in keywords:
                slug = kw.lower().replace(' ', '-')
                if kw.lower() in text or slug in href.lower():
                    subpage_url = urljoin(base_url, href)
                    break
            if subpage_url:
                break

        # fetch the subpage if found
        target_soup = soup
        if subpage_url:
            try:
                r2 = requests.get(subpage_url, timeout=8)
                r2.raise_for_status()
                target_soup = BeautifulSoup(r2.text, 'html.parser')
            except Exception:
                pass

        full_text = target_soup.get_text(" ").lower()
        # return only the keywords that actually appear
        return [kw for kw in keywords if kw.lower() in full_text]

    def fill_missing(self) -> pd.DataFrame:
        """
        For each of the three target columns, if a cell is NaN and the site URL exists,
        scrape and fill it with any found keywords (comma-joined).
        """
        for col, kws in self.mapping.items():
            mask = self.df[col].isna() & self.df[self.site_col].notna()
            for idx in self.df.index[mask]:
                url = self.df.at[idx, self.site_col]
                found = self.scrape_by_keywords(url, kws)
                if found:
                    self.df.at[idx, col] = ", ".join(found)
        return self.df


# --- Usage example ---

# assume you already computed:
#   sectors_list  = word_counts_sectors.index.tolist()
#   services_list = word_counts_services.index.tolist()
#   tech_list     = word_counts_tech.index.tolist()

scraper = CategoryScraper(
    df=df,
    site_col='Website',
    sector_keywords=sectors_list,
    service_keywords=services_list,
    tech_keywords=tech_list,
)

df_filled = scraper.fill_missing()
