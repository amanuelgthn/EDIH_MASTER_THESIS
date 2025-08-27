#!/usr/bin/python3

import pandas as pd
import re
from pathlib import Path
import matplotlib.pyplot as plt
import os

"""
SST Matrix Generator
--------------------
Reads Sheet 1 of the input Excel file, builds co-occurrence matrices for
- Sector × Service
- Service × Technology
- Sector × Technology
and Top-K × Top-K variants and row-penetration (%), then writes them to
`SST_matrices.xlsx`.

Additionally, it builds all 3D slices (fix one dimension among top-K and
cross-tab the remaining two) and writes them to `SST_3D_matrices.xlsx`,
while saving a heatmap PNG for each slice in `sst_heatmaps/`.

Edit the CONFIG block below as needed.
"""

# =========================
# CONFIG
# =========================
INPUT_FILE  = "combined_further_cleaned_keywords (1).xlsx"   # your data file
SHEET_NAME  = 0                                              # index or sheet name
OUTPUT_MAIN = "SST_matrices.xlsx"
OUTPUT_3D   = "SST_3D_matrices.xlsx"                         # the 3D slices workbook
HEATMAP_DIR = "sst_heatmaps"                                 # where PNGs go

# Column names in your data (adjust if headers differ)
SECTOR_COL  = "Sector"
SERVICE_COL = "Service"
TECH_COL    = "Technology"

# Split rules for multi-value cells
SPLIT_REGEX = r"[;,|]"

# Top-k for the “Top 5” views
TOP_K = 5

# =========================
# HELPERS
# =========================

def normalize_text(x: str):
    if not isinstance(x, str):
        return x
    x = x.strip()
    x = re.sub(r"\s+", " ", x)
    return x


def split_multi(s):
    if pd.isna(s):
        return []
    if isinstance(s, list):
        return s
    parts = re.split(SPLIT_REGEX, str(s))
    parts = [normalize_text(p) for p in parts if normalize_text(p)]
    return parts


def explode_multi(df, cols):
    out = df.copy()
    for c in cols:
        out[c] = out[c].apply(split_multi)
        out = out.explode(c, ignore_index=True)
    return out


def build_crosstab(df, row, col):
    ct = pd.crosstab(df[row], df[col]).sort_index()
    ct["__Row_Total__"] = ct.sum(axis=1)
    ct.loc["__Col_Total__"] = ct.sum(axis=0)
    return ct


def with_totals(df_):
    df2 = df_.copy()
    df2["__Row_Total__"] = df2.sum(axis=1)
    df2.loc["__Col_Total__"] = df2.sum(axis=0)
    return df2


def row_penetration(matrix_with_counts: pd.DataFrame) -> pd.DataFrame:
    df_counts = matrix_with_counts.copy()
    if "__Row_Total__" in df_counts.columns:
        df_counts = df_counts.drop(columns=["__Row_Total__"])
    if "__Col_Total__" in df_counts.index:
        df_counts = df_counts.drop(index="__Col_Total__")
    row_sum = df_counts.sum(axis=1).replace(0, pd.NA)
    pct = (df_counts.T / row_sum).T * 100
    return pct.round(2)


def safe_sheetname(name: str) -> str:
    name = re.sub(r"[\[\]\:\*\?\/\\]", "_", name)
    return name[:31]


def best_guess_col(possible_names, df_columns):
    lowered = {c.lower(): c for c in df_columns}
    for name in possible_names:
        for c_low, c_orig in lowered.items():
            if name.lower() in c_low:
                return c_orig
    return None


def plot_heatmap(matrix: pd.DataFrame, title: str, xlabel: str, ylabel: str, outpath: str):
    """Save an annotated heatmap for the **Top-K × Top-K** (default 5×5) sub-matrix.
    This does NOT affect the Excel outputs; it only trims the visualization.
    """
    # remove totals if present
    mat = matrix.copy()
    if "__Row_Total__" in mat.columns:
        mat = mat.drop(columns=["__Row_Total__"])
    if "__Col_Total__" in mat.index:
        mat = mat.drop(index="__Col_Total__")

    # pick top-K rows/cols by slice-internal sums
    k = min(TOP_K, max(mat.shape))
    top_rows = mat.sum(axis=1).sort_values(ascending=False).head(k).index
    top_cols = mat.sum(axis=0).sort_values(ascending=False).head(k).index
    mat = mat.loc[top_rows, top_cols]

    plt.figure(figsize=(8, 8))
    plt.imshow(mat.values, aspect='auto')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)

    plt.xticks(range(mat.shape[1]), mat.columns, rotation=90)
    plt.yticks(range(mat.shape[0]), mat.index)

    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            plt.text(j, i, str(mat.iat[i, j]), ha='center', va='center')

    plt.tight_layout()
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    plt.savefig(outpath, dpi=200)
    plt.close()


# =========================
# LOAD DATA
# =========================

def load_data():
    if not Path(INPUT_FILE).exists():
        raise FileNotFoundError(f"Could not find '{INPUT_FILE}' in the working directory.")

    df_raw = pd.read_excel(INPUT_FILE, sheet_name=SHEET_NAME)

    # Auto-detect headers if needed
    sec_col = SECTOR_COL if SECTOR_COL in df_raw.columns else best_guess_col(
        ["sector", "sectors", "formatted sector", "formatted sectors"], df_raw.columns
    )
    srv_col = SERVICE_COL if SERVICE_COL in df_raw.columns else best_guess_col(
        ["service", "services", "formatted service", "formatted services"], df_raw.columns
    )
    tec_col = TECH_COL if TECH_COL in df_raw.columns else best_guess_col(
        ["technology", "technologies", "formatted technology", "formatted technologies"], df_raw.columns
    )

    missing = [name for name, col in [(SECTOR_COL, sec_col), (SERVICE_COL, srv_col), (TECH_COL, tec_col)] if col is None]
    if missing:
        raise ValueError(
            "Could not find required columns. "
            f"Tried to locate {missing}. Columns present: {list(df_raw.columns)}"
        )

    df = df_raw[[sec_col, srv_col, tec_col]].rename(
        columns={sec_col: SECTOR_COL, srv_col: SERVICE_COL, tec_col: TECH_COL}
    )

    for c in [SECTOR_COL, SERVICE_COL, TECH_COL]:
        df[c] = df[c].apply(lambda x: normalize_text(x) if isinstance(x, str) else x)

    return df


# =========================
# MAIN PIPELINE
# =========================

def main():
    df = load_data()

    # Pairwise long forms
    df_ss = explode_multi(df[[SECTOR_COL, SERVICE_COL]].copy(), [SECTOR_COL, SERVICE_COL]).dropna()
    df_st = explode_multi(df[[SERVICE_COL, TECH_COL]].copy(),    [SERVICE_COL, TECH_COL]).dropna()
    df_xt = explode_multi(df[[SECTOR_COL, TECH_COL]].copy(),     [SECTOR_COL, TECH_COL]).dropna()

    # Triple long form (for 3D slices)
    df_long3 = explode_multi(df[[SECTOR_COL, SERVICE_COL, TECH_COL]].copy(), [SECTOR_COL, SERVICE_COL, TECH_COL]).dropna()

    # Full matrices
    ct_ss_full = build_crosstab(df_ss, SECTOR_COL,  SERVICE_COL)
    ct_st_full = build_crosstab(df_st, SERVICE_COL, TECH_COL)
    ct_xt_full = build_crosstab(df_xt, SECTOR_COL,  TECH_COL)

    # Top-K × Top-K
    top_sectors   = df_ss[SECTOR_COL].value_counts().head(TOP_K).index.tolist()
    top_services  = df_ss[SERVICE_COL].value_counts().head(TOP_K).index.tolist()
    top_services2 = df_st[SERVICE_COL].value_counts().head(TOP_K).index.tolist()
    top_techs2    = df_st[TECH_COL].value_counts().head(TOP_K).index.tolist()
    top_sectors2  = df_xt[SECTOR_COL].value_counts().head(TOP_K).index.tolist()
    top_techs3    = df_xt[TECH_COL].value_counts().head(TOP_K).index.tolist()

    ct_ss_top = with_totals(pd.crosstab(df_ss[SECTOR_COL], df_ss[SERVICE_COL]).loc[top_sectors, top_services])
    ct_st_top = with_totals(pd.crosstab(df_st[SERVICE_COL], df_st[TECH_COL]).loc[top_services2, top_techs2])
    ct_xt_top = with_totals(pd.crosstab(df_xt[SECTOR_COL], df_xt[TECH_COL]).loc[top_sectors2, top_techs3])

    # Penetration (%)
    ss_pct = row_penetration(ct_ss_full)
    st_pct = row_penetration(ct_st_full)
    xt_pct = row_penetration(ct_xt_full)

    # Write main workbook
    with pd.ExcelWriter(OUTPUT_MAIN, engine="openpyxl") as writer:
        ct_ss_full.to_excel(writer, sheet_name=safe_sheetname("Sector_Service_FULL"))
        ct_st_full.to_excel(writer, sheet_name=safe_sheetname("Service_Tech_FULL"))
        ct_xt_full.to_excel(writer, sheet_name=safe_sheetname("Sector_Tech_FULL"))

        ct_ss_top.to_excel(writer, sheet_name=safe_sheetname(f"Sect_Serv_TOP{TOP_K}"))
        ct_st_top.to_excel(writer, sheet_name=safe_sheetname(f"Serv_Tech_TOP{TOP_K}"))
        ct_xt_top.to_excel(writer, sheet_name=safe_sheetname(f"Sect_Tech_TOP{TOP_K}"))

        ss_pct.to_excel(writer, sheet_name=safe_sheetname("Sector_Service_%"))
        st_pct.to_excel(writer, sheet_name=safe_sheetname("Service_Tech_%"))
        xt_pct.to_excel(writer, sheet_name=safe_sheetname("Sector_Tech_%"))

    print(f"Wrote: {OUTPUT_MAIN}")

    # 3D Slices + Heatmaps
    os.makedirs(HEATMAP_DIR, exist_ok=True)
    slices_to_write = []  # (sheet_name, dataframe)

    # A) For each top service: Sector × Technology | Service = s
    top_services_all = df_st[SERVICE_COL].value_counts().head(TOP_K).index.tolist()
    for s in top_services_all:
        df_slice = df_long3[df_long3[SERVICE_COL] == s]
        mat = with_totals(pd.crosstab(df_slice[SECTOR_COL], df_slice[TECH_COL]))
        sheet = safe_sheetname(f"Sect×Tech|Srv={s}")
        slices_to_write.append((sheet, mat))
        plot_heatmap(mat, title=f"Sector × Technology (Service = {s})", xlabel="Technology", ylabel="Sector",
                     outpath=os.path.join(HEATMAP_DIR, f"sect_tech__service_{re.sub(r'[^A-Za-z0-9]+','_',s)}.png"))

    # B) For each top sector: Service × Technology | Sector = x
    top_sectors_all = df_ss[SECTOR_COL].value_counts().head(TOP_K).index.tolist()
    for x in top_sectors_all:
        df_slice = df_long3[df_long3[SECTOR_COL] == x]
        mat = with_totals(pd.crosstab(df_slice[SERVICE_COL], df_slice[TECH_COL]))
        sheet = safe_sheetname(f"Serv×Tech|Sec={x}")
        slices_to_write.append((sheet, mat))
        plot_heatmap(mat, title=f"Service × Technology (Sector = {x})", xlabel="Technology", ylabel="Service",
                     outpath=os.path.join(HEATMAP_DIR, f"serv_tech__sector_{re.sub(r'[^A-Za-z0-9]+','_',x)}.png"))

    # C) For each top technology: Sector × Service | Technology = t
    top_techs_all = df_st[TECH_COL].value_counts().head(TOP_K).index.tolist()
    for t in top_techs_all:
        df_slice = df_long3[df_long3[TECH_COL] == t]
        mat = with_totals(pd.crosstab(df_slice[SECTOR_COL], df_slice[SERVICE_COL]))
        sheet = safe_sheetname(f"Sect×Serv|Tech={t}")
        slices_to_write.append((sheet, mat))
        plot_heatmap(mat, title=f"Sector × Service (Technology = {t})", xlabel="Service", ylabel="Sector",
                     outpath=os.path.join(HEATMAP_DIR, f"sect_serv__tech_{re.sub(r'[^A-Za-z0-9]+','_',t)}.png"))

    # Write 3D workbook
    with pd.ExcelWriter(OUTPUT_3D, engine="openpyxl") as writer:
        for sheet, mat in slices_to_write:
            mat.to_excel(writer, sheet_name=sheet)

    print(f"Wrote: {OUTPUT_3D}")
    print(f"Saved heatmaps in: {HEATMAP_DIR}/")


if __name__ == "__main__":
    main()
