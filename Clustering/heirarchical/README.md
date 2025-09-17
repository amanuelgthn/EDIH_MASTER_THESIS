# Clustering (Hierarchical)

This folder contains a **two-step pipeline** for building country-level features from the EDIH catalogue and then clustering countries with **Ward’s hierarchical method**.

---

## 📂 Folder Structure

Clustering/
├─ data_preparation.py # STEP 1: build & standardize country features (X1–X5)
├─ clustering.py # STEP 2: Ward hierarchical clustering + reports
├─ combined_further_cleaned_keywords (1).xlsx # source Excel (example)
├─ country_features_raw.csv # produced by Step 1
├─ country_features_standardized.csv # produced by Step 1 (input to Step 2)
├─ clustering_outputs.xlsx # produced by Step 2
├─ dendrogram_ward.png # produced by Step 2

markdown
Copy code

---

## ⚙️ What the two scripts do

### 1) `data_preparation.py` (run this first)

**Goal:**  
Aggregate hub-level tags into country-level indicators and standardize them for clustering.

**Inputs (expected):**
- Excel file: `combined_further_cleaned_keywords (1).xlsx`
- Sheet1 with at least these columns:
  - `Country`
  - `Formatted sectors`
  - `Formatted services`
  - `Formatted technologies`

⚠️ By default the script parses these as **comma-separated lists**. If your file uses semicolons, edit `parse_list()` accordingly.

Also expects three analysis sheets (first column = label list; first 5 rows = Top-5):
- `services_Analysis`
- `sectors_Analysis`
- `technologies_Analysis`

**How it works (high level):**
- Reads per-hub lists of sectors / services / technologies.
- Builds **country aggregates** by unioning tags across each country’s hubs.
- Computes 5 features per country:
  - **X1_Breadth**: average unique coverage across sectors, services, technologies
  - **X2_Top5_Concentration**: share of tags in the Top-5 (from analysis sheets)
  - **X3_Advanced_Tech_Index**: share of advanced techs (AI, IoT, Digital Twins, HPC, Blockchain, Robotics)
  - **X4_ServiceMix_Index**: share of business/skills/ecosystem services (configurable set)
  - **X5_Distinctiveness_Index**: `1 − X2_Top5_Concentration`
- Standardizes X1–X5 (zero mean, unit variance) for Ward clustering.

**Outputs:**
- `country_features_raw.csv` — unscaled metrics (#EDIHs, X1–X5)
- `country_features_standardized.csv` — scaled X1–X5 (input to clustering)

**Key parameters to customize (top of the script):**
- `EXCEL_PATH, HUB_SHEET, SERV_TOP5_SHEET, SECT_TOP5_SHEET, TECH_TOP5_SHEET`
- `ADVANCED_TECHS` (set of strings matching normalized tech tokens)
- `BUSINESS_SERVICES` (set of services to include in X4)
- `parse_list()` if delimiter ≠ comma

---

### 2) `clustering.py` (run this second)

**Goal:**  
Perform **Ward hierarchical clustering** on the standardized features and export a full report.

**Inputs (expected):**
- `country_features_standardized.csv` — from Step 1  
- Required columns:
  - `Country`
  - `X1_Breadth, X2_Top5_Concentration, X3_Advanced_Tech_Index, X4_ServiceMix_Index, X5_Distinctiveness_Index`

**How it works (high level):**
- Loads the standardized feature table.
- Computes Ward linkage (`linkage(X, method="ward")`).
- Saves a dendrogram (PNG).
- Cuts the dendrogram at user-selected K values (`K_LIST = [3, 4]` by default).
- For each K, computes:
  - Cluster counts
  - Members (countries in each cluster)
  - Centroids (means of standardized features per cluster)
  - ANOVA (feature differences across clusters; F and p-values)
  - Silhouette: overall + per-country scores
  - WCSS (within-cluster sum of squares)

**Outputs:**
- `dendrogram_ward.png` — hierarchical tree (countries on leaves)
- `clustering_outputs.xlsx` — multi-sheet report:
  - `Country_Clusters` — features + cluster labels (for all K in K_LIST)
  - `Counts_k3`, `Members_k3`, `Centroids_k3`, `ANOVA_k3`, `Silhouette_k3_by_country`
  - `Counts_k4`, `Members_k4`, `Centroids_k4`, `ANOVA_k4`, `Silhouette_k4_by_country`
  - `Silhouette` — overall silhouette scores for each K
  - `WCSS_k3_k4` — cohesion summary

**Key parameters to customize (top of the script):**
- `STD_TABLE_PATH` — path to `country_features_standardized.csv`
- `OUT_EXCEL, OUT_DENDRO` — output filenames
- `FEATURES` — feature set used in clustering (default X1–X5)
- `K_LIST` — cluster counts to evaluate (e.g., `[3, 4, 5, 6]`)

---

## ⚡ Quick start

### Install dependencies
```bash
pip install pandas numpy scipy scikit-learn matplotlib XlsxWriter
(If you prefer openpyxl for Excel, change the writer engine accordingly.)

Run Step 1 – Data preparation
bash
Copy code
python data_preparation.py
This writes:

country_features_raw.csv

country_features_standardized.csv

Run Step 2 – Clustering
bash
Copy code
python clustering.py
This writes:

dendrogram_ward.png

clustering_outputs.xlsx

📑 File formats & assumptions
The Excel source (combined_further_cleaned_keywords (1).xlsx) must contain:

Sheet1 with hub catalogue + comma-separated tag lists:

Formatted sectors, Formatted services, Formatted technologies

Analysis sheets: services_Analysis, sectors_Analysis, technologies_Analysis
with the Top-5 labels in the first column (used for X2).

Country names taken from Sheet1 → Country column.

All tags lowercased in data prep — ensure your ADVANCED_TECHS and BUSINESS_SERVICES match normalized tokens.

📊 Interpreting the clustering report
Dendrogram: Look for big distance jumps to pick a sensible K.

Centroids (standardized): Which features are high/low in each cluster.

ANOVA: Features with low p-values differ most across clusters.

Silhouette: Closer to +1 = better separation; check per-country silhouettes.

WCSS: Lower values = tighter clusters (compare across K).

🛠 Troubleshooting
ModuleNotFoundError: No module named 'xlsxwriter'
Install it:

bash
Copy code
pip install XlsxWriter
(or switch writer engine to openpyxl in clustering.py).

KeyError: Sheet not found / column not found
Check Excel sheet/column names. Adjust EXCEL_PATH, *_SHEET, and parsing logic.

Delimiter mismatch
If tags separated by ; instead of ,, change parse_list():

python
Copy code
str(cell).split(";")
Empty or tiny clusters
Try different K_LIST values or review feature definitions (e.g., expand ADVANCED_TECHS or BUSINESS_SERVICES
