# Post_Scraping

This module contains scripts to process and refine the scraped EDIH dataset.  
It provides functionality to merge raw scrapes with older cleaned data, normalize keyword fields, validate counts, analyze keywords, and produce visualizations.

---

## Folder Structure

Post_Scraping/
├─ Scraped.xlsx # Newly scraped raw data
├─ preCleaned.xlsx # Older cleaned dataset
├─ combined.xlsx # Output of mergescraped.py
├─ combined_further.xlsx # Intermediate merged file
├─ combined_further_cleaned_keywords.xlsx# Final cleaned dataset
├─ export-edihs.xls # Original reference export
├─ temp_map.png # Output map visualization
│
├─ mergescraped.py
├─ post_cleanup.py
├─ count_occurrence.py
├─ keyword_analysis.py
├─ plotfigure.py


---

## Workflow (Recommended Order)

1. **`mergescraped.py`**  
   - **Purpose**: Merge the latest `Scraped.xlsx` with `preCleaned.xlsx`.  
   - **Input**:  
     - `preCleaned.xlsx` (sheet: `Cleaned_FULL`)  
     - `Scraped.xlsx`  
   - **Output**:  
     - `combined.xlsx` (merged dataset)  
   - **Run**:  
     ```bash
     python3 mergescraped.py
     ```

2. **`post_cleanup.py`**  
   - **Purpose**: Normalize keyword columns in the merged dataset.  
   - **Operations**:  
     - Lowercase tokens  
     - Remove numbers and special characters  
     - Collapse multiple spaces  
   - **Input**:  
     - `combined_further.xlsx` (intermediate file created from merged data)  
   - **Output**:  
     - `combined_further_cleaned_keywords.xlsx`  
   - **Run**:  
     ```bash
     python3 post_cleanup.py
     ```

3. **`count_occurrence.py`**  
   - **Purpose**: Count number of hubs per country.  
   - **Input**:  
     - `combined_further_cleaned_keywords.xlsx` (sheet: `Sheet1`)  
     - `export-edihs.xls` (reference)  
   - **Output** (sheets added to cleaned workbook):  
     - `Count` — counts from cleaned dataset  
     - `old Count` — counts from reference export  
   - **Run**:  
     ```bash
     python3 count_occurrence.py
     ```

4. **`keyword_analysis.py`**  
   - **Purpose**: Keyword frequency analysis for sectors, services, and technologies.  
   - **Input**:  
     - `combined_further_cleaned_keywords.xlsx`  
   - **Output** (sheets added to same workbook):  
     - `sectors_Analysis`  
     - `services_Analysis`  
     - `technologies_Analysis`  
   - **Run**:  
     ```bash
     python3 keyword_analysis.py
     ```

5. **`plotfigure.py`**  
   - **Purpose**: Create a country-level map of EDIH counts.  
   - **Input**:  
     - `combined_further_cleaned_keywords.xlsx` (sheet: `Count`)  
   - **Output**:  
     - `temp_map.png` (choropleth with counts labeled)  
   - **Run**:  
     ```bash
     python3 plotfigure.py
     ```

---

## Dependencies

Install dependencies with:

```bash
pip install pandas numpy openpyxl plotly pycountry Pillow geopy kaleido
pandas, numpy, openpyxl → data handling & Excel I/O

plotly, kaleido → choropleth & static image export

pycountry → country name → ISO mapping

Pillow → image manipulation

geopy → country centroid lookup for labels

Notes & Pitfalls
File locking: Close the Excel workbook before running scripts that append (count_occurrence.py, keyword_analysis.py).

Delimiters: Cleaning assumes comma-separated tags. Update regex in post_cleanup.py if ; or | are used.

Country names: Map generation requires standard country names resolvable by pycountry. Adjust names if some fail.

Nominatim rate limits: plotfigure.py uses a 1-second delay per country. The first run may be slow, but results are cached locally by geopy.

End Product
After running the pipeline you will have:

Cleaned dataset: combined_further_cleaned_keywords.xlsx

Country counts: Sheets Count and old Count

Keyword analysis: Sheets sectors_Analysis, services_Analysis, technologies_Analysis

Visualization: temp_map.png (choropleth of EDIHs per country)
