# SST Matrix Generator — README

This repository contains a single script, **`SST_Build.py`**, that:

- Reads your curated EDIH Excel file
- Converts multi-value categorical fields into co-occurrence matrices
- Exports:
  1. Pairwise SST tables (Sector×Service, Service×Technology, Sector×Technology)  
  2. 3-D slices of the full Sector–Service–Technology cube
- Saves annotated heatmaps for the most relevant slices

---

## What this script produces

### **SST_matrices.xlsx**

- **Sector_Service_FULL** — counts of hubs by Sector × Service  
- **Service_Tech_FULL** — counts of hubs by Service × Technology  
- **Sector_Tech_FULL** — counts of hubs by Sector × Technology  
- **Sect_Serv_TOPK** — TOP-K × TOP-K submatrix of Sector × Service (with totals)  
- **Serv_Tech_TOPK** — TOP-K × TOP-K submatrix of Service × Tech (with totals)  
- **Sect_Tech_TOPK** — TOP-K × TOP-K submatrix of Sector × Tech (with totals)  
- **Sector_Service_%** — row-penetration (percent) for Sector × Service  
- **Service_Tech_%** — row-penetration (percent) for Service × Tech  
- **Sector_Tech_%** — row-penetration (percent) for Sector × Tech  

**Notes:**
- Totals are labeled `Row_Total` (last column) and `Col_Total` (last row).  
- Row-penetration (%) = each cell ÷ row sum × 100 (after removing totals).

---

### **SST_3D_matrices.xlsx**

A collection of 2-D slices from the 3-D SST cube:

- **Sect×Tech | Srv=<service>** — Sector × Technology conditional on a given Service  
- **Serv×Tech | Sec=<sector>** — Service × Technology conditional on a given Sector  
- **Sect×Serv | Tech=<tech>** — Sector × Service conditional on a given Technology  

Each slice includes totals and corresponds to counts of hubs with (dimension A) **AND** (dimension B) **AND** the fixed (dimension C).

---

### **sst_heatmaps/**

For each slice above, a PNG heatmap with values annotated in the cells.  
Each heatmap shows the **Top-K rows** and **Top-K columns** within that slice (independent of other slices) for easy visual inspection.

---

## How it works (pipeline)

1. Load your Excel file and auto-detect the three key columns (**Sector, Service, Technology**).  
   - Defaults: `Sector`, `Service`, `Technology`  
   - If headers don’t exist, script tries “best guesses” (e.g., `formatted sectors`).  

2. Split multi-value cells using the regex:  

   ```python
   SPLIT_REGEX = r"[;,|]"
