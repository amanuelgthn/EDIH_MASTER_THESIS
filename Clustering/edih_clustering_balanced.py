#!/usr/bin/env python3
"""
Country-level SST Specialization — Hierarchical Clustering with Balance-Optimized Selection (k=3 & k=4)

- Input: 'combined_further_cleaned_keywords (1).xlsx' (Sheet 1)
- Renames:
    "Formatted sectors"       -> "Sector"
    "Formatted services"      -> "Service"
    "Formatted technologies"  -> "Technology"
  (Country auto-detected; adjust COUNTRY_HINTS if needed.)

- Country summary (exported):
    X1_total_hubs
    X2_num_sectors
    X3_num_services
    X4_num_technologies
    X5_sector_top5_share
    X6_tech_top5_share
    X7_service_top5_share

- Two hierarchical variants:
    A) Ward + Euclidean
    B) Average + Cosine

  For each k in {3,4}, the script:
    * computes cluster sizes, size-balance (normalized entropy), silhouette
    * penalizes tiny clusters below MIN_CLUSTER_SHARE
    * selects the variant with the highest composite score
    * exports chosen labels & top tables
    * also exports a comparison sheet with metrics for both methods

- Outputs:
    Excel: Country_clusters_hier_k3_k4_BALANCED.xlsx
    Plots: Country_cluster_plots_balanced/
"""

import os
import re
from pathlib import Path
import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler, normalize
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, pairwise_distances
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
from scipy.spatial.distance import pdist
import matplotlib.pyplot as plt

# =========================
# CONFIG
# =========================
INPUT_FILE     = "combined_further_cleaned_keywords (1).xlsx"
SHEET_NAME     = 0
OUTPUT_FILE    = "Country_clusters_hier_k3_k4_BALANCED.xlsx"  # engine=openpyxl

# Your exact headers
EXACT_RENAMES = {
    "Formatted sectors": "Sector",
    "Formatted services": "Service",
    "Formatted technologies": "Technology",
}

# Try to autodetect Country
COUNTRY_HINTS = ["country", "country (edih)", "edih country", "member state", "nation", "state"]

# Feature mode for country profiles
FEATURE_MODE   = "combined"  # "sectors" | "services" | "technologies" | "combined"

# Denoising & weighting
RARE_THRESHOLD = 5          # prune features appearing in < this many countries (after aggregation)
WEIGHT_SECTOR  = 1.0
WEIGHT_SERVICE = 1.8        # service weighting improves separation
WEIGHT_TECH    = 1.0

# Normalization & PCA
USE_ROW_L2     = True       # L2-normalize country rows (profile similarity)
USE_PCA        = True
PCA_COMPS_MAX  = 20

# Which k to materialize & evaluate
CUTS_K         = [3, 4]
RANDOM_STATE   = 42

# Balance-vs-separation tradeoff (0..1): higher = prefer balanced sizes
BALANCE_WEIGHT     = 0.6
# Penalize any cluster smaller than this share (e.g., 5% = 0.05)
MIN_CLUSTER_SHARE  = 0.05
PENALTY_PER_TINY   = 0.2   # subtract from composite score per under-sized cluster

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
    """One-hot encode a Series of list-like labels."""
    exploded = series.explode()
    cats = exploded.dropna().value_counts().index.tolist()
    data, idxs = [], []
    for idx, items in series.items():
        items = set(items or [])
        data.append([1 if c in items else 0 for c in cats])
        idxs.append(idx)
    return pd.DataFrame(data, index=idxs, columns=cats)

def dict_to_wide(df_map, title_prefix):
    frames = []
    for lab, ser in df_map.items():
        frames.append(ser.rename(f"{title_prefix} — Cluster {lab}"))
    return pd.concat(frames, axis=1) if frames else pd.DataFrame()

def top_counts_per_cluster(labels_df, feature_df, label_col, top_n=15):
    out = {}
    for lab in sorted(labels_df[label_col].unique()):
        idx = labels_df[labels_df[label_col] == lab].index
        sub = feature_df.loc[idx]
        counts = sub.sum(axis=0).sort_values(ascending=False).head(top_n)
        out[lab] = counts
    return out

def pca_scatter(X, labels, title, out_png):
    pts = PCA(n_components=2, random_state=RANDOM_STATE).fit_transform(X)
    plt.figure(figsize=(7, 6))
    for lab in np.unique(labels):
        mask = (labels == lab)
        plt.scatter(pts[mask, 0], pts[mask, 1], label=f"C{lab}", s=45)
    plt.xlabel("PC1"); plt.ylabel("PC2")
    plt.title(title); plt.legend()
    plt.tight_layout()
    os.makedirs("Country_cluster_plots_balanced", exist_ok=True)
    plt.savefig(out_png, dpi=180)
    plt.close()

def size_balance_metrics(labels, X_for_sil, metric="euclidean", precomputed=False):
    """Return sizes, proportions, normalized entropy (0..1), silhouette."""
    labels = np.asarray(labels)
    k = len(np.unique(labels))
    n = len(labels)
    sizes = np.array([(labels == c).sum() for c in sorted(np.unique(labels))])
    props = sizes / n
    # normalized entropy (0..1)
    with np.errstate(divide='ignore', invalid='ignore'):
        H = -(props * np.log(props + 1e-12)).sum()
    H_norm = H / np.log(k) if k > 1 else 0.0
    # silhouette
    if precomputed:
        sil = silhouette_score(X_for_sil, labels, metric="precomputed")
    else:
        sil = silhouette_score(X_for_sil, labels, metric=metric)
    return sizes, props, H_norm, sil

def composite_score(H_norm, sil, props, min_share=MIN_CLUSTER_SHARE, penalty_per=PENALTY_PER_TINY):
    score = BALANCE_WEIGHT * H_norm + (1.0 - BALANCE_WEIGHT) * sil
    tiny = (props < min_share).sum()
    score -= penalty_per * tiny
    return score, tiny

def build_top_tables(labels, X_sec_country, X_srv_country, X_tec_country, k, label_name):
    df_labels = pd.DataFrame({label_name: labels}, index=X_sec_country.index)
    def _tops(feature_df, prefix):
        m = top_counts_per_cluster(df_labels, feature_df.loc[df_labels.index], label_name, top_n=15)
        return dict_to_wide(m, prefix)
    top_sec = _tops(X_sec_country, f"{label_name}=k{k} — Top Sectors")
    top_srv = _tops(X_srv_country, f"{label_name}=k{k} — Top Services")
    top_tec = _tops(X_tec_country, f"{label_name}=k{k} — Top Technologies")
    return df_labels, top_sec, top_srv, top_tec

# =========================
# LOAD & RENAME
# =========================
if not Path(INPUT_FILE).exists():
    raise FileNotFoundError(f"Cannot find: {INPUT_FILE}")

df_raw = pd.read_excel(INPUT_FILE, sheet_name=SHEET_NAME)
df = df_raw.rename(columns=EXACT_RENAMES).copy()

# Detect/rename Country
if "Country" not in df.columns:
    guess = best_guess_col(COUNTRY_HINTS, df.columns)
    if guess is None:
        raise ValueError(
            "Could not detect a Country column.\n"
            f"Available columns: {list(df.columns)}\n"
            "Add your country column to COUNTRY_HINTS or rename it to 'Country'."
        )
    df = df.rename(columns={guess: "Country"})

# Validate
for req in ["Sector", "Service", "Technology", "Country"]:
    if req not in df.columns:
        raise ValueError(f"Missing required column after rename: {req}")

# Clean & split
for c in ["Sector", "Service", "Technology", "Country"]:
    df[c] = df[c].apply(lambda x: normalize_text(x) if isinstance(x, str) else x)
for c in ["Sector", "Service", "Technology"]:
    df[c] = df[c].apply(split_multi)
df = df.dropna(subset=["Country"])

# =========================
# HUB → COUNTRY AGGREGATION
# =========================
X_sec_hub = binarize_multilabel(df["Sector"])
X_srv_hub = binarize_multilabel(df["Service"])
X_tec_hub = binarize_multilabel(df["Technology"])

country_index = df["Country"].values
X_sec_country = pd.DataFrame(X_sec_hub.values, index=country_index, columns=X_sec_hub.columns).groupby(level=0).sum()
X_srv_country = pd.DataFrame(X_srv_hub.values, index=country_index, columns=X_srv_hub.columns).groupby(level=0).sum()
X_tec_country = pd.DataFrame(X_tec_hub.values, index=country_index, columns=X_tec_hub.columns).groupby(level=0).sum()

# =========================
# PRE-CLUSTERING SUMMARY X1..X7 (TOP-5 shares)
# =========================
def country_summary(df_in):
    rows = []
    for country, group in df_in.groupby("Country"):
        hubs = len(group)
        sec_all = group["Sector"].explode().dropna()
        srv_all = group["Service"].explode().dropna()
        tec_all = group["Technology"].explode().dropna()

        sectors  = set([s for lst in group["Sector"] for s in lst if s])
        services = set([s for lst in group["Service"] for s in lst if s])
        techs    = set([t for lst in group["Technology"] for t in lst if t])

        sec_shares = sec_all.value_counts(normalize=True)
        srv_shares = srv_all.value_counts(normalize=True)
        tec_shares = tec_all.value_counts(normalize=True)

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
# FEATURE SPACE (countries)
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

# Remove all-zero rows
Xc = Xc.loc[(Xc.sum(axis=1) > 0)]

# Rare-feature pruning
if RARE_THRESHOLD and RARE_THRESHOLD > 1:
    mask = (Xc.sum(axis=0) >= RARE_THRESHOLD)
    Xc = Xc.loc[:, mask]

# Row L2 normalization
if USE_ROW_L2:
    Xc = pd.DataFrame(
        normalize(Xc.values, norm="l2", axis=1),
        index=Xc.index, columns=Xc.columns
    )

# Standardize + optional PCA
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
# BUILD TWO TREES
# =========================
# A) Ward + Euclidean
Z_ward = linkage(Xc_emb, method="ward")
os.makedirs("country_cluster_plots", exist_ok=True)
plt.figure(figsize=(12, 6))
dendrogram(Z_ward, labels=Xc.index.tolist(), leaf_rotation=90)
plt.title("Dendrogram — Ward (Euclidean)")
plt.xlabel("Country"); plt.ylabel("Distance")
plt.tight_layout()
plt.savefig("country_cluster_plots/dendrogram_ward.png", dpi=200)
plt.close()

# B) Average + Cosine
D_cos = pdist(Xc_emb, metric="cosine")
Z_cosavg = linkage(D_cos, method="average")
plt.figure(figsize=(12, 6))
dendrogram(Z_cosavg, labels=Xc.index.tolist(), leaf_rotation=90)
plt.title("Dendrogram — Average (Cosine)")
plt.xlabel("Country"); plt.ylabel("Cosine distance")
plt.tight_layout()
plt.savefig("country_cluster_plots/dendrogram_cosine_avg.png", dpi=200)
plt.close()

# =========================
# EVALUATE & SELECT BEST (per k)
# =========================
comparison_rows = []
chosen = {}  # k -> dict with method, labels, metrics

for k in CUTS_K:
    # Ward
    labels_w = fcluster(Z_ward, t=k, criterion="maxclust")
    sizes_w, props_w, Hn_w, sil_w = size_balance_metrics(labels_w, Xc_emb, metric="euclidean", precomputed=False)
    score_w, tiny_w = composite_score(Hn_w, sil_w, props_w, MIN_CLUSTER_SHARE, PENALTY_PER_TINY)
    comparison_rows.append({
        "k": k, "Method": "Ward",
        "Sizes": "; ".join(map(str, sizes_w.tolist())),
        "MinShare": props_w.min(), "EntropyNorm": Hn_w,
        "Silhouette": sil_w, "TinyClusters(<{:.0%})".format(MIN_CLUSTER_SHARE): int(tiny_w),
        "CompositeScore": score_w
    })

    # CosineAvg
    labels_c = fcluster(Z_cosavg, t=k, criterion="maxclust")
    # silhouette with cosine distance on embedded space
    D_full = pairwise_distances(Xc_emb, metric="cosine")
    sizes_c, props_c, Hn_c, sil_c = size_balance_metrics(labels_c, D_full, metric="precomputed", precomputed=True)
    score_c, tiny_c = composite_score(Hn_c, sil_c, props_c, MIN_CLUSTER_SHARE, PENALTY_PER_TINY)
    comparison_rows.append({
        "k": k, "Method": "CosineAvg",
        "Sizes": "; ".join(map(str, sizes_c.tolist())),
        "MinShare": props_c.min(), "EntropyNorm": Hn_c,
        "Silhouette": sil_c, "TinyClusters(<{:.0%})".format(MIN_CLUSTER_SHARE): int(tiny_c),
        "CompositeScore": score_c
    })

    # Choose best method by composite score
    if score_c > score_w:
        chosen[k] = {
            "Method": "CosineAvg",
            "labels": labels_c,
            "sizes": sizes_c, "props": props_c,
            "EntropyNorm": Hn_c, "Silhouette": sil_c, "CompositeScore": score_c
        }
        pca_scatter(Xc_emb, labels_c, title=f"Countries — CosineAvg (k={k}) — chosen",
                    out_png=f"country_cluster_plots/CHOSEN_CosineAvg_k{k}_pca.png")
    else:
        chosen[k] = {
            "Method": "Ward",
            "labels": labels_w,
            "sizes": sizes_w, "props": props_w,
            "EntropyNorm": Hn_w, "Silhouette": sil_w, "CompositeScore": score_w
        }
        pca_scatter(Xc_emb, labels_w, title=f"Countries — Ward (k={k}) — chosen",
                    out_png=f"country_cluster_plots/CHOSEN_Ward_k{k}_pca.png")

comparison_df = pd.DataFrame(comparison_rows).sort_values(["k","CompositeScore"], ascending=[True, False])

# =========================
# BUILD TOP TABLES FOR CHOSEN PARTITIONS
# =========================
tops_by_k = {}   # k -> (labels_df, top_sec, top_srv, top_tec)
for k in CUTS_K:
    method = chosen[k]["Method"]
    labels = chosen[k]["labels"]
    label_name = f"CHOSEN_{method}_k{k}"
    lab_df, top_sec, top_srv, top_tec = build_top_tables(labels, X_sec_country, X_srv_country, X_tec_country, k, label_name)
    tops_by_k[k] = (lab_df, top_sec, top_srv, top_tec)

# =========================
# WRITE EXCEL
# =========================
with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
    # Country summary + Z
    summary_tbl.reset_index().to_excel(writer, sheet_name="Country_SST_Summary", index=False)
    from sklearn.preprocessing import StandardScaler as _SS
    _sc = _SS()
    z = pd.DataFrame(
        _sc.fit_transform(summary_tbl),
        index=summary_tbl.index, columns=[f"Z_{c}" for c in summary_tbl.columns]
    ).reset_index().rename(columns={"index": "Country"})
    z.to_excel(writer, sheet_name="Country_SST_Summary_Z", index=False)

    # Comparison of methods (sizes + metrics)
    comparison_df.to_excel(writer, sheet_name="Method_Comparison", index=False)

    # Chosen labels & tops for k=3 and k=4
    for k in CUTS_K:
        method = chosen[k]["Method"]
        labels = chosen[k]["labels"]
        sizes  = chosen[k]["sizes"]
        props  = chosen[k]["props"]
        summ = pd.DataFrame({
            "Cluster": list(range(1, len(sizes)+1)),
            "# Countries": sizes,
            "Share": np.round(props, 4)
        })
        summ["k"] = k; summ["Method"] = method
        summ.to_excel(writer, sheet_name=f"Chosen_Sizes_k{k}", index=False)

        lab_df, top_sec, top_srv, top_tec = tops_by_k[k]
        lab_df.reset_index().rename(columns={"index": "Country"}).to_excel(
            writer, sheet_name=f"Chosen_Labels_{method}_k{k}", index=False
        )
        top_sec.to_excel(writer, sheet_name=f"{method}_k{k}_Top_Sectors")
        top_srv.to_excel(writer, sheet_name=f"{method}_k{k}_Top_Services")
        top_tec.to_excel(writer, sheet_name=f"{method}_k{k}_Top_Technologies")

print(f"✅ Saved balanced clustering results to '{OUTPUT_FILE}'.")
print("📁 Dendrograms & PCA plots in 'Country_cluster_plots_balanced/'.")
