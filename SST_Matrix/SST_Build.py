#!/usr/bin/python3

import pandas as pd
import re
from pathlib import Path

# ===================== SETTINGS =====================
CANDIDATES = [
    "combined_further_cleaned_keywords (1).xlsx",
    "combined_further_cleaned_keywords.xlsx"
]
SHEET_RAW = "Sheet1"  # your main data
COL_SECTORS  = "Formatted sectors"
COL_SERVICES = "Formatted services"
COL_TECHS    = "Formatted technologies"

# Analysis sheets (rename if your workbook uses different labels)
SHEET_SECTOR_ANALYSIS = "sectors_Analysis"
SHEET_SERVICE_ANALYSIS = "services_Analysis"
SHEET_TECH_ANALYSIS = "technologies_Analysis"

# how many top tags to keep
TOP_N = 10

# Output
OUT_XLSX = "EDIH_one_hot_outputs_from_analysis.xlsx"
# ====================================================

def _load_first_existing(candidates):
    for p in candidates:
        path = Path(p)
        if path.exists():
            return path
    raise FileNotFoundError(f"None of these files found: {candidates}")

def _normalize(s: str) -> str:
    if pd.isna(s):
        return ""
    s = str(s).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _split_tags(cell):
    if pd.isna(cell) or str(cell).strip() == "":
        return []
    parts = re.split(r"[;,]\s*", str(cell))
    parts = [_normalize(x) for x in parts if x and str(x).strip() != ""]
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p); out.append(p)
    return out

def one_hot_from_listcol(series_of_lists, prefix):
    all_tags = sorted({tag for lst in series_of_lists for tag in lst})
    data = []
    for lst in series_of_lists:
        s = set(lst)
        row = [1 if tag in s else 0 for tag in all_tags]
        data.append(row)
    cols = [f"{prefix}_{t}" for t in all_tags]
    return pd.DataFrame(data, columns=cols, index=series_of_lists.index)

def _pick_metric_column(df, preferred_order=("Count","Coverage","Contribution","Cumulative")):
    """
    Try to pick the best numeric column for ranking top tags.
    Looks for exact or partial matches (case-insensitive) in order.
    """
    # Build a map of lower->original
    colmap = {c.lower(): c for c in df.columns}
    # First try exact preferred names (case-insensitive / contains)
    for key in preferred_order:
        # exact match
        for c in df.columns:
            if c.strip().lower() == key.strip().lower():
                return c
        # contains match
        for c in df.columns:
            if key.strip().lower() in c.strip().lower():
                return c
    # fallback: take the first numeric column
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            return c
    raise ValueError("No suitable numeric metric column found to rank Top-N.")

def _pick_label_column(df, preferred=("Formatted", "Name", "Label")):
    """
    Try to pick the label column (e.g., 'Formatted Sectors', 'Formatted Services').
    """
    # prefer a column that contains 'formatted' (case-insensitive)
    for c in df.columns:
        if "formatted" in c.lower():
            return c
    # next best: 'name' or 'label'
    for key in preferred:
        for c in df.columns:
            if key.lower() in c.lower():
                return c
    # else use the first non-numeric column
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]):
            return c
    raise ValueError("No suitable label column found in analysis sheet.")

def _get_topN_from_analysis(xls, sheetname, N=10):
    """
    Read an analysis sheet and return Top-N normalized labels
    based on the best available metric column.
    """
    df = pd.read_excel(xls, sheet_name=sheetname)
    label_col = _pick_label_column(df)
    metric_col = _pick_metric_column(df)

    tmp = df[[label_col, metric_col]].dropna()
    tmp[label_col] = tmp[label_col].apply(_normalize)

    # deduplicate (keep max metric per label if duplicates)
    tmp = tmp.groupby(label_col, as_index=False)[metric_col].max()
    # sort by metric desc
    tmp = tmp.sort_values(metric_col, ascending=False).head(N)
    return tmp[label_col].tolist()

# ---------- MAIN ----------
xls_path = _load_first_existing(CANDIDATES)

# 0) Load raw sheet
raw = pd.read_excel(xls_path, sheet_name=SHEET_RAW).copy()

# 1) Build normalized list-columns from raw
for col in [COL_SECTORS, COL_SERVICES, COL_TECHS]:
    if col not in raw.columns:
        raise KeyError(f"Expected column '{col}' not found in sheet '{SHEET_RAW}'.")
raw["sectors_list"]  = raw[COL_SECTORS].apply(_split_tags)
raw["services_list"] = raw[COL_SERVICES].apply(_split_tags)
raw["techs_list"]    = raw[COL_TECHS].apply(_split_tags)

# 2) One-hot encode FULL matrices
sectors_ohe_full  = one_hot_from_listcol(raw["sectors_list"],  "sector")
services_ohe_full = one_hot_from_listcol(raw["services_list"], "service")
techs_ohe_full    = one_hot_from_listcol(raw["techs_list"],    "tech")
X_full = pd.concat([sectors_ohe_full, services_ohe_full, techs_ohe_full], axis=1)

# 3) Extract Top-N directly from analysis sheets
top_sectors  = _get_topN_from_analysis(xls_path, SHEET_SECTOR_ANALYSIS,  N=TOP_N)
top_services = _get_topN_from_analysis(xls_path, SHEET_SERVICE_ANALYSIS, N=TOP_N)
top_techs    = _get_topN_from_analysis(xls_path, SHEET_TECH_ANALYSIS,    N=TOP_N)

# 4) Build Top-N filtered OHE matrices (keeping only those columns)
def _subset_ohe(ohe_df, prefix, keep_labels):
    keep_set = {f"{prefix}_{_normalize(k)}" for k in keep_labels}
    return ohe_df[[c for c in ohe_df.columns if c in keep_set]].copy()

sectors_ohe_top  = _subset_ohe(sectors_ohe_full,  "sector",  top_sectors)
services_ohe_top = _subset_ohe(services_ohe_full, "service", top_services)
techs_ohe_top    = _subset_ohe(techs_ohe_full,    "tech",    top_techs)
X_top = pd.concat([sectors_ohe_top, services_ohe_top, techs_ohe_top], axis=1)

# 5) Save all outputs
id_cols = [c for c in ["Hub Name", "EDIH Name", "Country", "ID"] if c in raw.columns]
with pd.ExcelWriter(OUT_XLSX, engine="xlsxwriter") as w:
    raw[id_cols + [COL_SECTORS, COL_SERVICES, COL_TECHS]].to_excel(w, sheet_name="original_fields", index=False)
    raw[id_cols + ["sectors_list","services_list","techs_list"]].to_excel(w, sheet_name="clean_lists", index=False)

    sectors_ohe_full.to_excel(w,  sheet_name="ohe_sectors_full",  index=False)
    services_ohe_full.to_excel(w, sheet_name="ohe_services_full", index=False)
    techs_ohe_full.to_excel(w,    sheet_name="ohe_techs_full",    index=False)
    X_full.to_excel(w,            sheet_name="ohe_combined_full", index=False)

    # Top-N dynamic (from analysis sheets)
    pd.DataFrame({"top_sectors": top_sectors}).to_excel(w,  sheet_name="topN_from_analysis", index=False, startrow=0)
    pd.DataFrame({"top_services": top_services}).to_excel(w, sheet_name="topN_from_analysis", index=False, startrow=0, startcol=2)
    pd.DataFrame({"top_techs": top_techs}).to_excel(w,      sheet_name="topN_from_analysis", index=False, startrow=0, startcol=4)

    sectors_ohe_top.to_excel(w,  sheet_name="ohe_sectors_topN",  index=False)
    services_ohe_top.to_excel(w, sheet_name="ohe_services_topN", index=False)
    techs_ohe_top.to_excel(w,    sheet_name="ohe_techs_topN",    index=False)
    X_top.to_excel(w,            sheet_name="ohe_combined_topN", index=False)

print("Done.\n",
      f"- Wrote full and Top-{TOP_N} 0/1 matrices to: {OUT_XLSX}\n",
      f"- Top-{TOP_N} derived from sheets: '{SHEET_SECTOR_ANALYSIS}', '{SHEET_SERVICE_ANALYSIS}', '{SHEET_TECH_ANALYSIS}'.")
