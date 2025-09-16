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
INPUT_FILE = "combined_further_cleaned_keywords (1).xlsx"
SHEET_NAME = 0 # or sheet name string
OUTPUT_FILE = "EDIH_clusters_enhanced.xlsx" # engine=openpyxl

ID_COL_CANDIDATES = ["name", "edih", "hub", "title"] # fuzzy match for an ID column
COUNTRY_COL_CANDIDATES = ["country", "countries", "location", "nation"] # fuzzy match for a country column

# Feature mode: "sectors" | "services" | "technologies" | "combined"
FEATURE_MODE = "combined"

# Denoising & weighting
RARE_THRESHOLD = 5 # drop features appearing in < this many hubs (try 3..10)
WEIGHT_SECTOR = 1.0
WEIGHT_SERVICE = 1.6 # upweighting services helps separation
WEIGHT_TECH = 1.0

# Normalization & PCA
USE_ROW_L2 = True # L2-normalize each row (profile-based)
USE_PCA = True # set False to skip
PCA_COMPS_MAX = 50 # cap number of PCA components

# K ranges & saving
K_RANGE = range(3, 13) # Updated to start from k=3
SAVE_LABELS_FOR = [3, 4, 5] # Export labels for k=3 and higher for comparison
RANDOM_STATE = 42

# =========================
# HELPERS
# =========================
def normalize_text(x):
    if not isinstance(x, str):
        return x
    x = x.strip()
    x = re.sub(r"\s+", " ", x)
    return x

def best_guess_col(possible_keywords, columns):
    cols = list(columns)
    lower_map = {c.lower(): c for c in cols}
    for kw in possible_keywords:
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
    series: pandas Series of list-like values
    returns: DataFrame with one-hot columns for each unique token (ordered by freq)
    """
    exploded = series.explode()
    cats = exploded.dropna().value_counts().index.tolist()
    data = []
    idxs = []
    for idx, items in series.items():
        items = set(items or [])
        data.append([1 if c in items else 0 for c in cats])
        idxs.append(idx)
    return pd.DataFrame(data, index=idxs, columns=cats)

def choose_id_column(df):
    cand = best_guess_col(ID_COL_CANDIDATES, df.columns)
    if cand is None:
        df = df.copy()
        df["Hub_ID"] = np.arange(len(df)) + 1
        return df, "Hub_ID"
    return df, cand

def silhouette_scan_euclidean(X, k_range, algo="kmeans"):
    """
    Return {k: {'score': silhouette, 'labels': np.array}}
    X: ndarray/2D
    """
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
    """
    Agglomerative with cosine distance (average linkage).
    Uses precomputed distance matrix for clustering and silhouette.
    """
    D = pairwise_distances(X, metric="cosine")
    out = {}
    for k in k_range:
        # For scikit-learn>=1.4, use metric="precomputed"; for <=1.3, use affinity="precomputed"
        model = AgglomerativeClustering(
            n_clusters=k,
            linkage="average",
            metric="precomputed"
        )
        labels = model.fit_predict(D)
        score = silhouette_score(D, labels, metric="precomputed")
        out[k] = {"score": score, "labels": labels}
    return out

def pca_embed(X, max_comps=PCA_COMPS_MAX):
    n_features = X.shape[1]
    n_comps = min(max_comps, n_features)
    if n_comps < 2:
        return X # not enough features to reduce
    pca = PCA(n_components=n_comps, random_state=RANDOM_STATE)
    return pca.fit_transform(X)

def pca_plot(X, labels, title, out_png):
    from sklearn.decomposition import PCA
    pts = PCA(n_components=2, random_state=RANDOM_STATE).fit_transform(X)
    plt.figure(figsize=(7, 6))
    for lab in np.unique(labels):
        mask = (labels == lab)
        plt.scatter(pts[mask, 0], pts[mask, 1], label=f"C{lab}", s=30)
    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    os.makedirs("cluster_plots", exist_ok=True)
    plt.savefig(out_png, dpi=180)
    plt.close()

def top_counts_per_cluster(df_labels, feature_df, label_col, top_n=10):
    out = {}
    for lab in sorted(df_labels[label_col].unique()):
        idx = df_labels[df_labels[label_col] == lab].index
        sub = feature_df.loc[idx]
        counts = sub.sum(axis=0).sort_values(ascending=False).head(top_n)
        out[lab] = counts
    return out

def dict_to_wide(df_map, title_prefix):
    frames = []
    for lab, ser in df_map.items():
        frames.append(ser.rename(f"{title_prefix} Cluster {lab}"))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1)

def top_countries_per_cluster(df_labels, country_series, label_col, top_n=10):
    out = {}
    for lab in sorted(df_labels[label_col].unique()):
        idx = df_labels[df_labels[label_col] == lab].index
        countries = country_series.loc[idx].value_counts().head(top_n)
        out[lab] = countries
    return out

# =========================
# LOAD & PREP
# =========================
if not Path(INPUT_FILE).exists():
    raise FileNotFoundError(f"Cannot find: {INPUT_FILE}")

raw = pd.read_excel(INPUT_FILE, sheet_name=SHEET_NAME)

# Auto-detect columns
sector_col = best_guess_col(["sector", "sectors"], raw.columns)
service_col = best_guess_col(["service", "services"], raw.columns)
tech_col = best_guess_col(["technolog"], raw.columns) # matches technology/technologies
country_col = best_guess_col(COUNTRY_COL_CANDIDATES, raw.columns)

missing = [n for n in ["Sector", "Service", "Technology"]
           if ((n == "Sector" and sector_col is None) or
               (n == "Service" and service_col is None) or
               (n == "Technology" and tech_col is None))]
if missing:
    raise ValueError(f"Missing required columns: {missing}. Found: {list(raw.columns)}")

df = raw.rename(columns={sector_col: "Sector", service_col: "Service", tech_col: "Technology"}).copy()
df, id_col = choose_id_column(df)

# Clean + split lists
for c in ["Sector", "Service", "Technology"]:
    df[c] = df[c].apply(lambda x: normalize_text(x) if isinstance(x, str) else x)
    df[c] = df[c].apply(split_multi)

# Binary features
X_sec = binarize_multilabel(df["Sector"])
X_srv = binarize_multilabel(df["Service"])
X_tec = binarize_multilabel(df["Technology"])

# Feature selection/combination
if FEATURE_MODE == "sectors":
    X = X_sec.copy()
elif FEATURE_MODE == "services":
    X = X_srv.copy()
elif FEATURE_MODE == "technologies":
    X = X_tec.copy()
else:
    # combined with block weighting
    X = pd.concat([
        X_sec.add_prefix("SEC|") * WEIGHT_SECTOR,
        X_srv.add_prefix("SRV|") * WEIGHT_SERVICE,
        X_tec.add_prefix("TEC|") * WEIGHT_TECH
    ], axis=1)

# Remove all-zero rows
X = X.loc[(X.sum(axis=1) > 0)]
df_aligned = df.loc[X.index].copy()

# Drop ultra-rare columns
if RARE_THRESHOLD is not None and RARE_THRESHOLD > 1:
    mask = (X.sum(axis=0) >= RARE_THRESHOLD)
    X = X.loc[:, mask]

# Row L2-normalize (profile similarity)
if USE_ROW_L2:
    X = pd.DataFrame(
        normalize(X.values, norm="l2", axis=1),
        index=X.index, columns=X.columns
    )

# Scale (for Euclidean KMeans) then optional PCA
scaler = StandardScaler(with_mean=True, with_std=True)
X_scaled = scaler.fit_transform(X.values)

if USE_PCA:
    X_emb = pca_embed(X_scaled, max_comps=PCA_COMPS_MAX)
else:
    X_emb = X_scaled

# =========================
# SCANS
# =========================
# KMeans (Euclidean) on X_emb
km_results = silhouette_scan_euclidean(X_emb, K_RANGE, algo="kmeans")
k_km_best = max(km_results, key=lambda k: km_results[k]["score"])
print(f"[KMeans (Euclid)] best k = {k_km_best}, silhouette = {km_results[k_km_best]['score']:.3f}")

# Agglomerative (Cosine) on normalized X (pre-PCA)
agg_cos_results = silhouette_scan_cosine(X.values, K_RANGE)
k_agg_best = max(agg_cos_results, key=lambda k: agg_cos_results[k]["score"])
print(f"[Agglo (Cosine)] best k = {k_agg_best}, silhouette = {agg_cos_results[k_agg_best]['score']:.3f}")

# =========================
# EXPORT LABELS for SELECTED Ks
# =========================
labels_export = {}
for k in SAVE_LABELS_FOR:
    # KMeans labels at k
    km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init="auto")
    km_labels = km.fit_predict(X_emb)
    labels_export[f"kmeans_k{k}"] = km_labels

    # Agglomerative (Cosine) labels at k
    D = pairwise_distances(X.values, metric="cosine")
    agg = AgglomerativeClustering(n_clusters=k, linkage="average", metric="precomputed")
    agg_labels = agg.fit_predict(D)
    labels_export[f"aggcos_k{k}"] = agg_labels

# Attach “best” labels too
df_aligned["cluster_kmeans_bestk"] = km_results[k_km_best]["labels"]
df_aligned["cluster_aggcos_bestk"] = agg_cos_results[k_agg_best]["labels"]

# Also attach the chosen SAVE_LABELS_FOR
for key, labs in labels_export.items():
    df_aligned[key] = labs

# Pretty print lists to strings
if country_col:
    pretty = df_aligned[[id_col, country_col, "Sector", "Service", "Technology"] + list(df_aligned.columns[-(2 + len(labels_export)):])].copy()
else:
    pretty = df_aligned[[id_col, "Sector", "Service", "Technology"] + list(df_aligned.columns[-(2 + len(labels_export)):])].copy()
for c in ["Sector", "Service", "Technology"]:
    pretty[c] = pretty[c].apply(lambda xs: ", ".join(xs))

# =========================
# SUMMARY TABLES (Top 10)
# =========================
def build_summaries(df_labels, label_col):
    s_sec = dict_to_wide(top_counts_per_cluster(df_labels, X_sec.loc[df_labels.index], label_col, 10),
                         f"{label_col} — Top Sectors")
    s_srv = dict_to_wide(top_counts_per_cluster(df_labels, X_srv.loc[df_labels.index], label_col, 10),
                         f"{label_col} — Top Services")
    s_tec = dict_to_wide(top_counts_per_cluster(df_labels, X_tec.loc[df_labels.index], label_col, 10),
                         f"{label_col} — Top Technologies")
    return s_sec, s_srv, s_tec

km_sec, km_srv, km_tec = build_summaries(df_aligned, "cluster_kmeans_bestk")
ag_sec, ag_srv, ag_tec = build_summaries(df_aligned, "cluster_aggcos_bestk")

# Silhouette tables
km_sil_tbl = pd.DataFrame({"k": list(K_RANGE),
                           "silhouette": [km_results[k]["score"] for k in K_RANGE]})
agg_sil_tbl = pd.DataFrame({"k": list(K_RANGE),
                            "silhouette": [agg_cos_results[k]["score"] for k in K_RANGE]})

# Country summaries (if column found)
if country_col:
    km_countries = dict_to_wide(top_countries_per_cluster(df_aligned, df[country_col], "cluster_kmeans_bestk"),
                                "KM_BestK_Top_Countries")
    ag_countries = dict_to_wide(top_countries_per_cluster(df_aligned, df[country_col], "cluster_aggcos_bestk"),
                                "AGCos_BestK_Top_Countries")

# =========================
# PCA PLOTS (for best ks)
# =========================
os.makedirs("cluster_plots", exist_ok=True)
pca_plot(X_emb, km_results[k_km_best]["labels"],
         title=f"PCA: KMeans Euclid (k={k_km_best}) — {FEATURE_MODE}",
         out_png=f"cluster_plots/kmeans_bestk_pca.png")
# For cosine agglomerative, plot on X_emb just for visualization
pca_plot(X_emb, agg_cos_results[k_agg_best]["labels"],
         title=f"PCA: Agglo Cosine (k={k_agg_best}) — {FEATURE_MODE}",
         out_png=f"cluster_plots/aggcos_bestk_pca.png")

# =========================
# WRITE EXCEL
# =========================
with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
    pretty.to_excel(writer, sheet_name="Labeled_Hubs", index=False)

    km_sil_tbl.to_excel(writer, sheet_name="Silhouette_KMeans", index=False)
    agg_sil_tbl.to_excel(writer, sheet_name="Silhouette_AggCos", index=False)

    km_sec.to_excel(writer, sheet_name="KM_BestK_Top_Sectors")
    km_srv.to_excel(writer, sheet_name="KM_BestK_Top_Services")
    km_tec.to_excel(writer, sheet_name="KM_BestK_Top_Technologies")

    ag_sec.to_excel(writer, sheet_name="AGCos_BestK_Top_Sectors")
    ag_srv.to_excel(writer, sheet_name="AGCos_BestK_Top_Services")
    ag_tec.to_excel(writer, sheet_name="AGCos_BestK_Top_Technologies")

    if country_col:
        km_countries.to_excel(writer, sheet_name="KM_BestK_Top_Countries")
        ag_countries.to_excel(writer, sheet_name="AGCos_BestK_Top_Countries")

print(f"Saved enhanced results to '{OUTPUT_FILE}' and plots to 'cluster_plots/'.")
print(f"KMeans best k = {k_km_best}; Agglo-Cosine best k = {k_agg_best}")