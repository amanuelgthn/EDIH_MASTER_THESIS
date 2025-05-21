#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict
import pandas as pd
import asyncio

# you’ll need to install these two:
# pip install googletrans==4.0.0-rc1 scikit-learn
from googletrans import Translator
from sklearn.feature_extraction.text import CountVectorizer

class CategoryScraper:
    def __init__(
        self,
        df: pd.DataFrame,
        site_col: str,
        sector_keywords: List[str],
        service_keywords: List[str],
        tech_keywords: List[str],
        translator: Translator = None
    ):
        self.df = df.copy()
        self.site_col = site_col
        self.mapping: Dict[str, List[str]] = {
            'Formatted sectors': sector_keywords,
            'Formatted services': service_keywords,
            'Formatted technologies': tech_keywords,
        }
        # one single Translator instance for all calls
        self.translator = translator or Translator()

    def _get_translated_text(self, url: str) -> str:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        raw = soup.get_text(separator=' ', strip=True)

        coro = self.translator.translate(raw, dest='en')
        loop = asyncio.get_event_loop()
        translation = loop.run_until_complete(coro)
        return translation.text.lower()

    def scrape_and_translate(self, base_url: str) -> str:
        """
        Get the “main” text to analyze:
        1) look for a subpage link matching any keyword slug
        2) fetch that page if present
        3) translate whole thing into English
        """
        # step 1: initial fetch
        r = requests.get(base_url, timeout=8); r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')

        # look for a keyword-slug link to follow
        subpage = None
        for col, kws in self.mapping.items():
            for a in soup.select('a[href]'):
                href = a['href']
                text = a.get_text(" ", strip=True).lower()
                for kw in kws:
                    slug = kw.lower().replace(' ', '-')
                    if slug in href.lower() or kw.lower() in text:
                        subpage = urljoin(base_url, href)
                        break
                if subpage:
                    break
            if subpage:
                break

        # pick which URL to translate  
        return self._get_translated_text(subpage or base_url)

    def extract_top_n(
        self,
        text: str,
        keywords: List[str],
        top_n: int = 20
    ) -> List[str]:
        """
        Count only tokens in `keywords` and return the top_n by frequency.
        """
        # build lowercase vocabulary
        vocab = [kw.lower() for kw in keywords]

        vec = CountVectorizer(
            vocabulary=vocab,
            lowercase=True,
            token_pattern=r'\b\w+(?:\s+\w+)*\b'
        )
        X = vec.fit_transform([text])
        counts = X.sum(axis=0).A1
        tokens = vec.get_feature_names_out()

        # sort descending by count and take top_n
        freq = sorted(zip(tokens, counts), key=lambda x: -x[1])
        return [tok for tok, _ in freq[:top_n]]

    def fill_missing(self) -> pd.DataFrame:
        """
        For each missing cell, translate & scrape, then extract only from the
        pre-defined keywords for that column.
        """
        for col, kws in self.mapping.items():
            mask = self.df[col].isna() & self.df[self.site_col].notna()
            for idx in self.df.index[mask]:
                url = self.df.at[idx, self.site_col]
                top_keywords: List[str] = []
                try:
                    en_text = self.scrape_and_translate(url)
                    # pass in the specific keyword list for this column
                    top_keywords = self.extract_top_n(en_text, kws, top_n=10)
                    self.df.at[idx, col] = ", ".join(top_keywords)
                except Exception as e:
                    print(f"Error on {url}: {e} (skipping)")
                    continue
        return self.df

# --- Usage ---
# scraper = CategoryScraper(
#     df=df,
#     site_col='Website',
#     sector_keywords=sectors_list,
#     service_keywords=services_list,
#     tech_keywords=tech_list,
# )
# df_filled = scraper.fill_missing()
