#!/usr/bin/env python3
"""
Country-level SST Specialization Clustering (Top-5 shares)

- Reads 'combined_further_cleaned_keywords (1).xlsx' (Sheet 1)
- Renames your exact headers:
    "Formatted sectors"       -> "Sector"
    "Formatted services"      -> "Service"
    "Formatted technologies"  -> "Technology"
  Country column is auto-detected; adjust COUNTRY_HINTS if needed.
- Splits multi-value cells; aggregates hub features to COUNTRY profiles
- Summary table:
    X1_total_hubs
    X2_num_sectors
    X3_num_services
    X4_num_technologies
    X5_sector_top5_share
    X6_tech_top5_share
    X7_service_top5_share
- Clustering:
    * Computes silhouette for a K range (for reference)
    * Forces k = 4 for final labels (both KMeans and Agglo-Cosine)
- Outputs:
    Excel: Country_clusters.xlsx (openpyxl)
    Plots: country_cluster_plots/

Run:
    python edih_clustering_country.py
"""

import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler, normalize
from sklearn.metrics import silhouette_score, pairwise_distances
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans, AgglomerativeClustering

import matplotlib.pyplot as plt

# =========================
# CONFIG
# =========================
INPUT_FILE     = "combined_further_cleaned_keywords (1).xlsx"
SHEET_NAME     = 0  # or sheet name string
OUTPUT_FILE    = "Country_clusters.xlsx"  # engine=openpyxl

# Your exact headers (we rename to canonical names)
EXACT_RENAMES = {
    "Formatted sectors": "Sector",
    "Formatted services": "Service",
    "Formatted technologies": "Technology",
}

# Try to autodetect the Country column (first match wins)
COUNTRY_HINTS = [
    "country", "country (edih)", "edih country", "member state", "nation", "state"
]

# Feature mode for country profiles: "sectors" | "services" | "technologies" | "combined"
FEATURE_MODE   = "combined"

# Denoising & weighting
RARE_THRESHOLD = 3          # drop features that appear in < this many countries (after aggregation)
WEIGHT_SECTOR  = 1.0
WEIGHT_SERVICE = 1.6
WEIGHT_TECH    = 1.0

# Normalization & PCA
USE_ROW_L2     = True       # L2-normalize each country row (profile similarity)
USE_PCA        = True       # set False to skip
PCA_COMPS_MAX  = 30

# K scans (for reporting) and final K to enforce
K_RANGE        = range(2, 11)  # 2..10 (scan just for info)
FORCE_K        = 4             # final labels & summaries use k=4
RANDOM_STATE   = 42

# =========================
# HELPERS
# =========================
def normalize_text(x):
    if not isinstance(x, str):
        return x
    return re.sub(r"\s+", " ", x.strip())

def best_guess_col(possible_keywords, columns):
    lower_map = {c.lower(): c for c in columns}
    for kw in possible_keywords:
        kw = kw.lower()
        for c_low, c_orig in lower_map.items():
            if kw in c_low:
                return c_orig
    return None

SPLIT_REGEX = r"[;,|]"
def split_multi(val):
    if pd.isna(val):
        return []
    if isinstance(val, list):
        return val
    parts = re.split(SPLIT_REGEX, str(val))
    parts = [normalize_text(p) for p in parts if normalize_text(p)]
    return parts

def binarize_multilabel(series):
    """
    series: pandas Series of list-like values per hub
    returns: DataFrame with one-hot columns for each unique token (ordered by freq)
    """
    exploded = series.explode()
    cats = exploded.dropna().value_counts().index.tolist()
    data, idxs = [], []
    for idx, items in series.items():
        items = set(items or [])
        data.append([1 if c in items else 0 for c in cats])
        idxs.append(idx)
    return pd.DataFrame(data, index=idxs, columns=cats)

def silhouette_scan_euclidean(X, k_range, algo="kmeans"):
    out = {}
    for k in k_range:
        if algo == "kmeans":
            model = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init="auto")
            labels = model.fit_predict(X)
        else:
            model = AgglomerativeClustering(n_clusters=k, linkage="ward")
            labels = model.fit_predict(X)
        score = silhouette_score(X, labels, metric="euclidean")
        out[k] = {"score": score, "labels": labels}
    return out

def silhouette_scan_cosine(X, k_range):
    D = pairwise_distances(X, metric="cosine")
    out = {}
    for k in k_range:
        model = AgglomerativeClustering(n_clusters=k, linkage="average", metric="precomputed")
        labels = model.fit_predict(D)
        score = silhouette_score(D, labels, metric="precomputed")
        out[k] = {"score": score, "labels": labels}
    return out

def pca_plot(X, labels, title, out_png):
    pts = PCA(n_components=2, random_state=RANDOM_STATE).fit_transform(X)
    plt.figure(figsize=(7, 6))
    for lab in np.unique(labels):
        mask = (labels == lab)
        plt.scatter(pts[mask, 0], pts[mask, 1], label=f"C{lab}", s=45)
    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    os.makedirs("country_cluster_plots", exist_ok=True)
    plt.savefig(out_png, dpi=180)
    plt.close()

def top_counts_per_cluster(labels_df, feature_df, label_col, top_n=15):
    out = {}
    for lab in sorted(labels_df[label_col].unique()):
        idx = labels_df[labels_df[label_col] == lab].index
        sub = feature_df.loc[idx]
        counts = sub.sum(axis=0).sort_values(ascending=False).head(top_n)
        out[lab] = counts
    return out

def dict_to_wide(df_map, title_prefix):
    frames = []
    for lab, ser in df_map.items():
        frames.append(ser.rename(f"{title_prefix} Cluster {lab}"))
    return pd.concat(frames, axis=1) if frames else pd.DataFrame()

# =========================
# LOAD & RENAME
# =========================
if not Path(INPUT_FILE).exists():
    raise FileNotFoundError(f"Cannot find: {INPUT_FILE}")

df_raw = pd.read_excel(INPUT_FILE, sheet_name=SHEET_NAME)

# Rename your exact headers (prevents KeyError: 'Sector')
df = df_raw.rename(columns=EXACT_RENAMES).copy()

# Auto-detect the Country column if not present
if "Country" not in df.columns:
    guess = best_guess_col(COUNTRY_HINTS, df.columns)
    if guess is None:
        raise ValueError(
            "Could not detect a Country column.\n"
            f"Available columns: {list(df.columns)}\n"
            "Add your country column name to COUNTRY_HINTS or rename it to 'Country'."
        )
    df = df.rename(columns={guess: "Country"})

# Confirm required columns exist
for req in ["Sector", "Service", "Technology", "Country"]:
    if req not in df.columns:
        raise ValueError(f"Missing required column after rename: {req}")

# Normalize text and split multi-values
for c in ["Sector", "Service", "Technology", "Country"]:
    df[c] = df[c].apply(lambda x: normalize_text(x) if isinstance(x, str) else x)

for c in ["Sector", "Service", "Technology"]:
    df[c] = df[c].apply(split_multi)

# Drop rows missing Country
df = df.dropna(subset=["Country"])

# =========================
# HUB-LEVEL BINARY, THEN AGGREGATE TO COUNTRY
# =========================
X_sec_hub = binarize_multilabel(df["Sector"])
X_srv_hub = binarize_multilabel(df["Service"])
X_tec_hub = binarize_multilabel(df["Technology"])

country_index = df["Country"].values
X_sec_country = pd.DataFrame(X_sec_hub.values, index=country_index, columns=X_sec_hub.columns).groupby(level=0).sum()
X_srv_country = pd.DataFrame(X_srv_hub.values, index=country_index, columns=X_srv_hub.columns).groupby(level=0).sum()
X_tec_country = pd.DataFrame(X_tec_hub.values, index=country_index, columns=X_tec_hub.columns).groupby(level=0).sum()

# =========================
# PRE-CLUSTERING SUMMARY (X1..X7 with TOP-5 shares)
# =========================
def country_summary(df_in):
    """
    Summary per country:
    - X1..X4: counts
    - X5..X7: top-5 concentration shares (sector, technology, service)
    """
    rows = []
    for country, group in df_in.groupby("Country"):
        hubs = len(group)
        # Flatten
        sec_all = group["Sector"].explode().dropna()
        srv_all = group["Service"].explode().dropna()
        tec_all = group["Technology"].explode().dropna()
        # Unique counts
        sectors  = set([s for lst in group["Sector"] for s in lst if s])
        services = set([s for lst in group["Service"] for s in lst if s])
        techs    = set([t for lst in group["Technology"] for t in lst if t])
        # Shares
        sec_shares = sec_all.value_counts(normalize=True)
        srv_shares = srv_all.value_counts(normalize=True)
        tec_shares = tec_all.value_counts(normalize=True)
        # Top-5 sums (renamed to X5..X7)
        top_sec5 = sec_shares.head(5).sum() if not sec_shares.empty else np.nan
        top_tec5 = tec_shares.head(5).sum() if not tec_shares.empty else np.nan
        top_srv5 = srv_shares.head(5).sum() if not srv_shares.empty else np.nan

        rows.append({
            "Country": country,
            "X1_total_hubs": hubs,
            "X2_num_sectors": len(sectors),
            "X3_num_services": len(services),
            "X4_num_technologies": len(techs),
            "X5_sector_top5_share": top_sec5,
            "X6_tech_top5_share": top_tec5,
            "X7_service_top5_share": top_srv5
        })
    return pd.DataFrame(rows).set_index("Country").sort_index()

summary_tbl = country_summary(df)

# =========================
# FEATURE SPACE FOR COUNTRIES (for clustering)
# =========================
if FEATURE_MODE == "sectors":
    Xc = X_sec_country.copy()
elif FEATURE_MODE == "services":
    Xc = X_srv_country.copy()
elif FEATURE_MODE == "technologies":
    Xc = X_tec_country.copy()
else:
    Xc = pd.concat([
        X_sec_country.add_prefix("SEC|") * WEIGHT_SECTOR,
        X_srv_country.add_prefix("SRV|") * WEIGHT_SERVICE,
        X_tec_country.add_prefix("TEC|") * WEIGHT_TECH
    ], axis=1)

# Remove all-zero rows (just in case)
Xc = Xc.loc[(Xc.sum(axis=1) > 0)]

# Rare-feature pruning across countries
if RARE_THRESHOLD and RARE_THRESHOLD > 1:
    mask = (Xc.sum(axis=0) >= RARE_THRESHOLD)
    Xc = Xc.loc[:, mask]

# Row L2 normalization (profile-based similarity)
if USE_ROW_L2:
    Xc = pd.DataFrame(
        normalize(Xc.values, norm="l2", axis=1),
        index=Xc.index, columns=Xc.columns
    )

# Scale + optional PCA for Euclidean KMeans
scaler = StandardScaler(with_mean=True, with_std=True)
Xc_scaled = scaler.fit_transform(Xc.values)

if USE_PCA:
    n_feats = Xc_scaled.shape[1]
    n_comps = min(PCA_COMPS_MAX, n_feats) if n_feats >= 2 else n_feats
    if n_comps >= 2:
        Xc_emb = PCA(n_components=n_comps, random_state=RANDOM_STATE).fit_transform(Xc_scaled)
    else:
        Xc_emb = Xc_scaled
else:
    Xc_emb = Xc_scaled

# =========================
# SCANS (for reference only)
# =========================
km_scan = silhouette_scan_euclidean(Xc_emb, K_RANGE, algo="kmeans")
agg_scan = silhouette_scan_cosine(Xc.values, K_RANGE)
print(f"[Country KMeans (Euclid)] best k = {max(km_scan, key=lambda k: km_scan[k]['score'])}, silhouette = {km_scan[max(km_scan, key=lambda k: km_scan[k]['score'])]['score']:.3f}")
print(f"[Country Agglo (Cosine)] best k = {max(agg_scan, key=lambda k: agg_scan[k]['score'])}, silhouette = {agg_scan[max(agg_scan, key=lambda k: agg_scan[k]['score'])]['score']:.3f}")

# =========================
# FINAL LABELS — FORCE k = 4
# =========================
best_labels = pd.DataFrame(index=Xc.index)

km_model = KMeans(n_clusters=FORCE_K, random_state=RANDOM_STATE, n_init="auto")
best_labels["cluster_kmeans_k4"] = km_model.fit_predict(Xc_emb)

D = pairwise_distances(Xc.values, metric="cosine")
agg_model = AgglomerativeClustering(n_clusters=FORCE_K, linkage="average", metric="precomputed")
best_labels["cluster_aggcos_k4"] = agg_model.fit_predict(D)

# =========================
# SUMMARIES (Top 15 per cluster, using raw country counts)
# =========================
def build_summaries(labels_df, label_col):
    s_sec = dict_to_wide(
        top_counts_per_cluster(labels_df, X_sec_country.loc[labels_df.index], label_col, 15),
        f"{label_col} — Top Sectors"
    )
    s_srv = dict_to_wide(
        top_counts_per_cluster(labels_df, X_srv_country.loc[labels_df.index], label_col, 15),
        f"{label_col} — Top Services"
    )
    s_tec = dict_to_wide(
        top_counts_per_cluster(labels_df, X_tec_country.loc[labels_df.index], label_col, 15),
        f"{label_col} — Top Technologies"
    )
    return s_sec, s_srv, s_tec

km_sec, km_srv, km_tec = build_summaries(best_labels, "cluster_kmeans_k4")
ag_sec, ag_srv, ag_tec = build_summaries(best_labels, "cluster_aggcos_k4")

# =========================
# PCA PLOTS (k=4)
# =========================
os.makedirs("country_cluster_plots", exist_ok=True)
pca_plot(Xc_emb, best_labels["cluster_kmeans_k4"].values,
         title=f"Countries — KMeans Euclid (k=4) — {FEATURE_MODE}",
         out_png="country_cluster_plots/kmeans_k4_countries.png")
pca_plot(Xc_emb, best_labels["cluster_aggcos_k4"].values,
         title=f"Countries — Agglo Cosine (k=4) — {FEATURE_MODE}",
         out_png="country_cluster_plots/aggcos_k4_countries.png")

# =========================
# EXPORT EXCEL
# =========================
with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
    # Country labels (k=4)
    out_labels = best_labels.reset_index().rename(columns={"index": "Country"})
    out_labels.to_excel(writer, sheet_name="Country_Labels_k4", index=False)

    # Silhouette scans (reference)
    km_sil_tbl = pd.DataFrame({"k": list(K_RANGE),
                               "silhouette": [km_scan[k]["score"] for k in K_RANGE]})
    ag_sil_tbl = pd.DataFrame({"k": list(K_RANGE),
                               "silhouette": [agg_scan[k]["score"] for k in K_RANGE]})
    km_sil_tbl.to_excel(writer, sheet_name="Silhouette_KMeans_scan", index=False)
    ag_sil_tbl.to_excel(writer, sheet_name="Silhouette_AggCos_scan", index=False)

    # Pre-clustering summary (X1..X7 with top-5 shares) + Z-scores
    summary_tbl.reset_index().to_excel(writer, sheet_name="Country_SST_Summary", index=False)
    from sklearn.preprocessing import StandardScaler as _SS
    scaler2 = _SS()
    z = pd.DataFrame(
        scaler2.fit_transform(summary_tbl),
        index=summary_tbl.index, columns=[f"Z_{c}" for c in summary_tbl.columns]
    ).reset_index().rename(columns={"index": "Country"})
    z.to_excel(writer, sheet_name="Country_SST_Summary_Z", index=False)

    # Cluster summaries (k=4)
    km_sec.to_excel(writer, sheet_name="KM_k4_Top_Sectors")
    km_srv.to_excel(writer, sheet_name="KM_k4_Top_Services")
    km_tec.to_excel(writer, sheet_name="KM_k4_Top_Technologies")

    ag_sec.to_excel(writer, sheet_name="AGCos_k4_Top_Sectors")
    ag_srv.to_excel(writer, sheet_name="AGCos_k4_Top_Services")
    ag_tec.to_excel(writer, sheet_name="AGCos_k4_Top_Technologies")

print(f"Saved country-level results to '{OUTPUT_FILE}' and plots to 'country_cluster_plots/'.")
print("Final clustering enforced at k=4 (KMeans & Agglo-Cosine).")
