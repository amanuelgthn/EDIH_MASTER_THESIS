#!/usr/bin/env python3
"""
Country-level SST Specialization — Hierarchical Clustering (k = 2..6)
with Diversity Features (Shannon Entropy) and Multi-Metric Model Selection

Adds:
  X8_sector_entropy, X9_tech_entropy, X10_service_entropy
to Country_SST_Summary, and (optionally) uses them in clustering.

Inputs:
  - 'combined_further_cleaned_keywords (1).xlsx' (Sheet 1)
  - Columns mapped to:
      "Formatted sectors"       -> "Sector"
      "Formatted services"      -> "Service"
      "Formatted technologies"  -> "Technology"
    Country auto-detected (COUNTRY_HINTS).

Outputs:
  - Excel: Country_clusters_hier_k2_k6_ENTROPY.xlsx
  - Plots: country_cluster_plots_entropy/
"""

import os
import re
from pathlib import Path
import numpy as np
import pandas as pd

from scipy.stats import entropy
from sklearn.preprocessing import StandardScaler, normalize
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score, pairwise_distances
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
from scipy.spatial.distance import pdist
import matplotlib.pyplot as plt

# =========================
# CONFIG
# =========================
INPUT_FILE     = "combined_further_cleaned_keywords (1).xlsx"
SHEET_NAME     = 0
OUTPUT_FILE    = "Country_clusters_hier_k2_k6_ENTROPY.xlsx"
PLOT_DIR       = "country_cluster_plots_entropy"

# Canonical names
EXACT_RENAMES = {
    "Formatted sectors": "Sector",
    "Formatted services": "Service",
    "Formatted technologies": "Technology",
}
COUNTRY_HINTS = ["country", "country (edih)", "edih country", "member state", "nation", "state"]

# Feature mode: build profiles from these blocks
FEATURE_MODE   = "combined"  # "sectors" | "services" | "technologies" | "combined"

# Denoising & weighting of profile blocks
RARE_THRESHOLD = 5
WEIGHT_SECTOR  = 1.0
WEIGHT_SERVICE = 1.8
WEIGHT_TECH    = 1.0

# Use entropy features in clustering?
INCLUDE_ENTROPY_IN_FEATURES = True
# Optional weights for entropy block (when included)
WEIGHT_ENTROPY_BLOCK = 1.0   # keep 1.0 first; tune later if needed

# Normalization & PCA
USE_ROW_L2     = True
USE_PCA        = True
PCA_COMPS_MAX  = 20

# Scan range and forced outputs
K_SCAN         = list(range(2, 7))   # 2..6
FORCE_OUTPUT_K = [3, 4, 5, 6]
RANDOM_STATE   = 42

# Scoring weights (composite)
BALANCE_WEIGHT     = 0.50  # normalized entropy of sizes
SIL_WEIGHT         = 0.35  # silhouette (normalized per k)
CH_WEIGHT          = 0.10  # Calinski-Harabasz (normalized per k)
DB_WEIGHT          = 0.05  # inverted Davies-Bouldin (normalized per k)
MIN_CLUSTER_SHARE  = 0.05  # tiny cluster threshold
PENALTY_PER_TINY   = 0.2   # penalty per tiny cluster

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
    exploded = series.explode()
    cats = exploded.dropna().value_counts().index.tolist()
    data, idxs = [], []
    for idx, items in series.items():
        items = set(items or [])
        data.append([1 if c in items else 0 for c in cats])
        idxs.append(idx)
    return pd.DataFrame(data, index=idxs, columns=cats)

def pca_scatter(X, labels, title, out_png_name):
    os.makedirs(PLOT_DIR, exist_ok=True)
    pts = PCA(n_components=2, random_state=RANDOM_STATE).fit_transform(X)
    plt.figure(figsize=(7, 6))
    for lab in np.unique(labels):
        m = (labels == lab)
        plt.scatter(pts[m, 0], pts[m, 1], label=f"C{lab}", s=45)
    plt.xlabel("PC1"); plt.ylabel("PC2")
    plt.title(title); plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, out_png_name), dpi=180)
    plt.close()

def sizes_props_entropy(labels):
    labels = np.asarray(labels)
    k = len(np.unique(labels))
    n = len(labels)
    sizes = np.array([(labels == c).sum() for c in sorted(np.unique(labels))])
    props = sizes / n
    with np.errstate(divide='ignore', invalid='ignore'):
        H = -(props * np.log(props + 1e-12)).sum()
    H_norm = H / np.log(k) if k > 1 else 0.0
    return sizes, props, H_norm

def build_top_tables(labels, X_sec_country, X_srv_country, X_tec_country, k, label_name):
    df_labels = pd.DataFrame({label_name: labels}, index=X_sec_country.index)
    def _tops(feature_df, prefix, top_n=15):
        out = {}
        for lab in sorted(df_labels[label_name].unique()):
            idx = df_labels[df_labels[label_name] == lab].index
            counts = feature_df.loc[idx].sum(axis=0).sort_values(ascending=False).head(top_n)
            out[lab] = counts.rename(f"{prefix} — Cluster {lab}")
        return pd.concat(out, axis=1) if out else pd.DataFrame()
    top_sec = _tops(X_sec_country, f"{label_name}=k{k} — Top Sectors")
    top_srv = _tops(X_srv_country, f"{label_name}=k{k} — Top Services")
    top_tec = _tops(X_tec_country, f"{label_name}=k{k} — Top Technologies")
    return df_labels, top_sec, top_srv, top_tec

def minmax(x):
    x = np.array(x, dtype=float)
    lo, hi = np.nanmin(x), np.nanmax(x)
    if hi - lo < 1e-12:
        return np.ones_like(x) * 0.5
    return (x - lo) / (hi - lo)

# =========================
# LOAD
# =========================
if not Path(INPUT_FILE).exists():
    raise FileNotFoundError(f"Cannot find: {INPUT_FILE}")

df_raw = pd.read_excel(INPUT_FILE, sheet_name=SHEET_NAME).copy()
df = df_raw.rename(columns=EXACT_RENAMES)

if "Country" not in df.columns:
    guess = best_guess_col(COUNTRY_HINTS, df.columns)
    if guess is None:
        raise ValueError(f"Country column not found. Columns: {list(df.columns)}")
    df = df.rename(columns={guess: "Country"})

for c in ["Sector", "Service", "Technology", "Country"]:
    df[c] = df[c].apply(lambda x: normalize_text(x) if isinstance(x, str) else x)
for c in ["Sector", "Service", "Technology"]:
    df[c] = df[c].apply(split_multi)
df = df.dropna(subset=["Country"])

# =========================
# HUB -> COUNTRY AGGREGATES
# =========================
X_sec_hub = binarize_multilabel(df["Sector"])
X_srv_hub = binarize_multilabel(df["Service"])
X_tec_hub = binarize_multilabel(df["Technology"])

country_index = df["Country"].values
X_sec_country = pd.DataFrame(X_sec_hub.values, index=country_index, columns=X_sec_hub.columns).groupby(level=0).sum()
X_srv_country = pd.DataFrame(X_srv_hub.values, index=country_index, columns=X_srv_hub.columns).groupby(level=0).sum()
X_tec_country = pd.DataFrame(X_tec_hub.values, index=country_index, columns=X_tec_hub.columns).groupby(level=0).sum()

# =========================
# SUMMARY X1..X10 (Top-5 + Entropy)
# =========================
def country_summary_with_entropy(df_in):
    rows = []
    for country, g in df_in.groupby("Country"):
        hubs = len(g)

        sec_all = g["Sector"].explode().dropna()
        srv_all = g["Service"].explode().dropna()
        tec_all = g["Technology"].explode().dropna()

        sectors  = set([s for lst in g["Sector"] for s in lst if s])
        services = set([s for lst in g["Service"] for s in lst if s])
        techs    = set([t for lst in g["Technology"] for t in lst if t])

        sec_sh = sec_all.value_counts(normalize=True)
        srv_sh = srv_all.value_counts(normalize=True)
        tec_sh = tec_all.value_counts(normalize=True)

        top_sec5 = sec_sh.head(5).sum() if not sec_sh.empty else np.nan
        top_tec5 = tec_sh.head(5).sum() if not tec_sh.empty else np.nan
        top_srv5 = srv_sh.head(5).sum() if not srv_sh.empty else np.nan

        sh_sec = float(entropy(sec_sh)) if not sec_sh.empty else np.nan
        sh_srv = float(entropy(srv_sh)) if not srv_sh.empty else np.nan
        sh_tec = float(entropy(tec_sh)) if not tec_sh.empty else np.nan

        rows.append({
            "Country": country,
            "X1_total_hubs": hubs,
            "X2_num_sectors": len(sectors),
            "X3_num_services": len(services),
            "X4_num_technologies": len(techs),
            "X5_sector_top5_share": top_sec5,
            "X6_tech_top5_share": top_tec5,
            "X7_service_top5_share": top_srv5,
            "X8_sector_entropy": sh_sec,
            "X9_tech_entropy": sh_tec,
            "X10_service_entropy": sh_srv,
        })
    return pd.DataFrame(rows).set_index("Country").sort_index()

summary_tbl = country_summary_with_entropy(df)

# =========================
# FEATURE MATRIX (countries)
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

# Optionally append entropy features to the profile space
if INCLUDE_ENTROPY_IN_FEATURES:
    ent_df = summary_tbl[["X8_sector_entropy", "X9_tech_entropy", "X10_service_entropy"]].copy()
    # scale to similar magnitude as profile counts before row L2
    ent_df = (ent_df - ent_df.mean()) / (ent_df.std(ddof=0) + 1e-9)
    ent_df = ent_df * WEIGHT_ENTROPY_BLOCK
    Xc = Xc.join(ent_df, how="left")

# Remove all-zero rows
Xc = Xc.loc[(Xc.sum(axis=1) > 0)]

# Rare-feature pruning on profile columns only
if RARE_THRESHOLD and RARE_THRESHOLD > 1:
    # keep the entropy columns regardless
    keep_cols = list(Xc.columns)
    entropy_cols = [c for c in Xc.columns if c.startswith("X8_") or c.startswith("X9_") or c.startswith("X10_")]
    prof_cols = [c for c in keep_cols if c not in entropy_cols]
    mask = (Xc[prof_cols].sum(axis=0) >= RARE_THRESHOLD)
    Xc = pd.concat([Xc.loc[:, mask.index[mask]], Xc[entropy_cols]], axis=1)

# Row L2 normalization (profile similarity)
if USE_ROW_L2:
    Xc = pd.DataFrame(normalize(Xc.values, norm="l2", axis=1), index=Xc.index, columns=Xc.columns)

# Standardize + optional PCA
scaler = StandardScaler()
Xc_scaled = scaler.fit_transform(Xc.values)

if USE_PCA:
    n_feats = Xc_scaled.shape[1]
    n_comps = min(PCA_COMPS_MAX, n_feats) if n_feats >= 2 else n_feats
    Xc_emb = PCA(n_components=n_comps, random_state=RANDOM_STATE).fit_transform(Xc_scaled) if n_comps >= 2 else Xc_scaled
else:
    Xc_emb = Xc_scaled

# =========================
# TREES + DENDROGRAMS
# =========================
os.makedirs(PLOT_DIR, exist_ok=True)

Z_ward   = linkage(Xc_emb, method="ward")
plt.figure(figsize=(12, 6))
dendrogram(Z_ward, labels=Xc.index.tolist(), leaf_rotation=90)
plt.title("Dendrogram — Ward (Euclidean)")
plt.xlabel("Country"); plt.ylabel("Distance")
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "dendrogram_ward.png"), dpi=200)
plt.close()

D_cos    = pdist(Xc_emb, metric="cosine")
Z_cosavg = linkage(D_cos, method="average")
plt.figure(figsize=(12, 6))
dendrogram(Z_cosavg, labels=Xc.index.tolist(), leaf_rotation=90)
plt.title("Dendrogram — Average (Cosine)")
plt.xlabel("Country"); plt.ylabel("Cosine distance")
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "dendrogram_cosine_avg.png"), dpi=200)
plt.close()

# =========================
# SCAN k = 2..6 & SCORE
# =========================
rows = []
candidates = {}  # (k,method) -> dict

for k in K_SCAN:
    # Ward
    lab_w = fcluster(Z_ward, t=k, criterion="maxclust")
    sizes_w, props_w, Hn_w = sizes_props_entropy(lab_w)
    sil_w = silhouette_score(Xc_emb, lab_w, metric="euclidean")
    ch_w  = calinski_harabasz_score(Xc_emb, lab_w)
    db_w  = davies_bouldin_score(Xc_emb, lab_w)
    candidates[(k, "Ward")] = dict(labels=lab_w, sizes=sizes_w, props=props_w, Hn=Hn_w, sil=sil_w, ch=ch_w, db=db_w)

    # CosineAvg
    lab_c = fcluster(Z_cosavg, t=k, criterion="maxclust")
    D_full = pairwise_distances(Xc_emb, metric="cosine")
    sizes_c, props_c, Hn_c = sizes_props_entropy(lab_c)
    sil_c = silhouette_score(D_full, lab_c, metric="precomputed")
    ch_c  = calinski_harabasz_score(Xc_emb, lab_c)
    db_c  = davies_bouldin_score(Xc_emb, lab_c)
    candidates[(k, "CosineAvg")] = dict(labels=lab_c, sizes=sizes_c, props=props_c, Hn=Hn_c, sil=sil_c, ch=ch_c, db=db_c)

# Build comparison rows with normalized metrics per k
def add_rows_for_k(k):
    k_items = [(m, candidates[(k, m)]) for m in ["Ward", "CosineAvg"]]
    sils = [it[1]["sil"] for it in k_items]
    chs  = [it[1]["ch"] for it in k_items]
    dbs  = [it[1]["db"] for it in k_items]
    hns  = [it[1]["Hn"] for it in k_items]

    sil_n = minmax(sils)
    ch_n  = minmax(chs)
    db_inv = [1.0/x if x > 0 else 0.0 for x in dbs]
    db_n  = minmax(db_inv)
    hn_n  = hns  # already 0..1

    out = []
    for i,(method, res) in enumerate(k_items):
        tiny = (res["props"] < MIN_CLUSTER_SHARE).sum()
        composite = (BALANCE_WEIGHT*hn_n[i] +
                     SIL_WEIGHT*sil_n[i] +
                     CH_WEIGHT*ch_n[i] +
                     DB_WEIGHT*db_n[i] -
                     PENALTY_PER_TINY*tiny)
        out.append({
            "k": k, "Method": method,
            "Sizes": "; ".join(map(str, res["sizes"].tolist())),
            "MinShare": float(res["props"].min()),
            "EntropyNorm": float(res["Hn"]),
            "Silhouette": float(res["sil"]),
            "CalinskiHarabasz": float(res["ch"]),
            "DaviesBouldin": float(res["db"]),
            "TinyClusters(<{:.0%})".format(MIN_CLUSTER_SHARE): int(tiny),
            "Score_Balance": float(hn_n[i]),
            "Score_Sil": float(sil_n[i]),
            "Score_CH": float(ch_n[i]),
            "Score_DBinv": float(db_n[i]),
            "CompositeScore": float(composite),
        })
    return out

for k in K_SCAN:
    rows.extend(add_rows_for_k(k))

comparison_df = pd.DataFrame(rows).sort_values(["k","CompositeScore"], ascending=[True, False])

# pick best per k
chosen = {}
for k in K_SCAN:
    slice_k = comparison_df[comparison_df["k"]==k].sort_values("CompositeScore", ascending=False)
    best_method = slice_k.iloc[0]["Method"]
    chosen[(k, best_method)] = candidates[(k, best_method)]

# =========================
# EXPORT (chosen + forced)
# =========================
def build_top_for(k, method):
    res = chosen[(k, method)]
    labels = res["labels"]
    label_name = f"CHOSEN_{method}_k{k}"
    lab_df, top_sec, top_srv, top_tec = build_top_tables(labels, X_sec_country, X_srv_country, X_tec_country, k, label_name)
    pca_scatter(Xc_emb, labels, title=f"Countries — {method} (k={k}) — chosen", out_png_name=f"CHOSEN_{method}_k{k}_pca.png")
    return lab_df, top_sec, top_srv, top_tec

def forced_output(k, method):
    res = candidates[(k, method)]
    labels = res["labels"]
    label_name = f"FORCED_{method}_k{k}"
    lab_df, top_sec, top_srv, top_tec = build_top_tables(labels, X_sec_country, X_srv_country, X_tec_country, k, label_name)
    pca_scatter(Xc_emb, labels, title=f"Countries — {method} (k={k}) — forced", out_png_name=f"FORCED_{method}_k{k}_pca.png")
    return lab_df, top_sec, top_srv, top_tec

with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
    # Summary + z-scored summary
    summary_tbl.reset_index().to_excel(writer, sheet_name="Country_SST_Summary", index=False)
    z = pd.DataFrame(StandardScaler().fit_transform(summary_tbl),
                     index=summary_tbl.index, columns=[f"Z_{c}" for c in summary_tbl.columns]) \
            .reset_index().rename(columns={"index":"Country"})
    z.to_excel(writer, sheet_name="Country_SST_Summary_Z", index=False)

    # Comparison
    comparison_df.to_excel(writer, sheet_name="Model_Comparison_k2_to_k6", index=False)

    # Chosen per k (k=2..6)
    for k in K_SCAN:
        best_row = comparison_df[comparison_df["k"]==k].sort_values("CompositeScore", ascending=False).iloc[0]
        method = best_row["Method"]
        res = chosen[(k, method)]
        sizes = res["sizes"]; props = res["props"]

        # sizes
        pd.DataFrame({
            "Cluster": list(range(1, len(sizes)+1)),
            "# Countries": sizes,
            "Share": np.round(props, 4),
            "k": k, "Method": method
        }).to_excel(writer, sheet_name=f"Chosen_Sizes_k{k}", index=False)

        # labels + tops
        lab_df, top_sec, top_srv, top_tec = build_top_for(k, method)
        lab_df.reset_index().rename(columns={"index":"Country"}).to_excel(writer, sheet_name=f"Chosen_Labels_{method}_k{k}", index=False)
        top_sec.to_excel(writer, sheet_name=f"{method}_k{k}_Top_Sectors")
        top_srv.to_excel(writer, sheet_name=f"{method}_k{k}_Top_Services")
        top_tec.to_excel(writer, sheet_name=f"{method}_k{k}_Top_Technologies")

    # Forced outputs for k = 3,4,5,6 (both methods)
    for k in FORCE_OUTPUT_K:
        for method in ["Ward","CosineAvg"]:
            lab_df, top_sec, top_srv, top_tec = forced_output(k, method)
            lab_df.reset_index().rename(columns={"index":"Country"}).to_excel(writer, sheet_name=f"FORCED_Labels_{method}_k{k}", index=False)
            top_sec.to_excel(writer, sheet_name=f"FORCED_{method}_k{k}_Top_Sectors")
            top_srv.to_excel(writer, sheet_name=f"FORCED_{method}_k{k}_Top_Services")
            top_tec.to_excel(writer, sheet_name=f"FORCED_{method}_k{k}_Top_Technologies")

print(f"✅ Saved to '{OUTPUT_FILE}'.")
print(f"📁 Plots in '{PLOT_DIR}/'.")
