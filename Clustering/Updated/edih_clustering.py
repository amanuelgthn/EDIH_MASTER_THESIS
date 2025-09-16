#!/usr/bin/env python3
"""
EDIH clustering from the first sheet (sectors + services + technologies).

Input file is fixed: 'combined_further_cleaned_keywords (1).xlsx'

Important:
- Clustering is performed on the ACTUAL multi-hot features built from Sheet1 (no PCA).
- PCA is used ONLY to produce x1, x2 for a pre-clustering table and for visualization.
"""

import warnings
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt


INPUT_FILE = "combined_further_cleaned_keywords (1).xlsx"
SHEET_NAME = "Sheet1"
OUTPUT_CSV = "edih_clusters.csv"
OUTPUT_KEYWORDS = "cluster_top_keywords.csv"
OUTPUT_PLOT = "edih_clusters_2d.png"
OUTPUT_PREPARED = "edih_prepared_features.csv"
KMIN, KMAX = 6, 12
PCA_COMPONENTS = 20


def read_data(path: str, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet)
    for col in ["Formatted sectors", "Formatted services", "Formatted technologies"]:
        if col in df.columns:
            df[col] = df[col].fillna("")
        else:
            df[col] = ""
    df["all_keywords"] = (
        df.get("Formatted sectors", "").astype(str) + ", " +
        df.get("Formatted services", "").astype(str) + ", " +
        df.get("Formatted technologies", "").astype(str)
    )
    return df


def build_multi_hot(text_series: pd.Series):
    vectorizer = CountVectorizer(
        tokenizer=lambda x: [t.strip() for t in str(x).split(",") if str(t).strip()],
        token_pattern=None,
        lowercase=True
    )
    X = vectorizer.fit_transform(text_series)
    return X, vectorizer


def choose_k_by_silhouette(X_raw: np.ndarray, kmin: int, kmax: int):
    """
    Choose K using silhouette *on the actual multi-hot features* (no PCA).
    Returns (best_k, best_model, scores)
    """
    scores = {}
    best_k = None
    best_model = None
    best_score = -1
    for k in range(kmin, kmax + 1):
        model = KMeans(n_clusters=k, random_state=42, n_init=20)
        labels = model.fit_predict(X_raw)
        if len(np.unique(labels)) <= 1 or X_raw.shape[0] <= k:
            scores[k] = np.nan
            continue
        score = silhouette_score(X_raw, labels)
        scores[k] = score
        if np.isnan(score):
            continue
        if score > best_score:
            best_score = score
            best_k = k
            best_model = model
    return best_k, best_model, scores


def top_keywords_per_cluster(X, labels, feature_names, top_n=12):
    clusters = np.unique(labels)
    rows = []
    X_dense = X.toarray() if hasattr(X, "toarray") else X
    for c in clusters:
        idx = np.where(labels == c)[0]
        if len(idx) == 0:
            continue
        counts = X_dense[idx].sum(axis=0)
        order = np.argsort(counts)[::-1]
        tops = [(feature_names[i], int(counts[i])) for i in order[:top_n] if counts[i] > 0]
        for rank, (kw, cnt) in enumerate(tops, 1):
            rows.append({"cluster": int(c), "rank": rank, "keyword": kw, "count": cnt})
    out = pd.DataFrame(rows).sort_values(["cluster", "rank"])
    return out


def plot_2d_scatter(coords_2d, labels, title, path):
    plt.figure(figsize=(8, 6))
    plt.scatter(coords_2d[:, 0], coords_2d[:, 1], s=18, c=labels)
    plt.title(title)
    plt.xlabel("Component 1")
    plt.ylabel("Component 2")
    uniq = np.unique(labels)
    for u in uniq:
        plt.scatter([], [], label=f"Cluster {u}")
    plt.legend(loc="best", fontsize=8, markerscale=1.2, frameon=False)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def main():
    df = read_data(INPUT_FILE, SHEET_NAME)
    X, vectorizer = build_multi_hot(df["all_keywords"])
    feature_names = np.array(vectorizer.get_feature_names_out())

    # --- PCA ONLY FOR VISUALIZATION / PRE-CLUSTER TABLE ---
    n_samples, n_features = X.shape
    n_comp = min(PCA_COMPONENTS, n_samples, n_features)
    pca = PCA(n_components=n_comp, random_state=42)
    X_reduced = pca.fit_transform(X.toarray())

    # Save prepared features before clustering (x1, x2 from PCA)
    prepared_df = pd.DataFrame({
        "EDIH Title": df.get("EDIH Title", pd.Series(range(len(df)))),
        "Country": df.get("Country", ""),
    })
    prepared_df["x1"] = X_reduced[:, 0]
    prepared_df["x2"] = X_reduced[:, 1] if X_reduced.shape[1] > 1 else 0
    prepared_df.to_csv(OUTPUT_PREPARED, index=False)

    # --- CLUSTER ON ACTUAL MULTI-HOT FEATURES (NO PCA) ---
    X_dense = X.toarray()
    best_k, best_model, scores = choose_k_by_silhouette(X_dense, KMIN, KMAX)
    if best_model is None:
        raise RuntimeError("Failed to fit any KMeans model on raw features. Try different K range or check data.")
    labels = best_model.predict(X_dense)

    out_df = pd.DataFrame({
        "EDIH Title": df.get("EDIH Title", pd.Series(range(len(df)))),
        "Country": df.get("Country", ""),
        "Cluster": labels
    })
    out_df.to_csv(OUTPUT_CSV, index=False)

    kw_df = top_keywords_per_cluster(X, labels, feature_names, top_n=15)
    kw_df.to_csv(OUTPUT_KEYWORDS, index=False)

    # 2D plot still uses PCA coords for visualization only
    coords_2d = X_reduced[:, :2] if X_reduced.shape[1] >= 2 else np.c_[X_reduced[:, 0], np.zeros(len(X_reduced))]
    plot_2d_scatter(coords_2d, labels, f"EDIH Clusters on Raw Features (K={best_k})", OUTPUT_PLOT)

    print(f"Best K selected by silhouette (raw features): {best_k}")
    print("Silhouette scores by K (raw features):")
    for k in range(KMIN, KMAX + 1):
        print(f"  K={k}: {scores.get(k)}")
    print(f"\nSaved prepared features (x1,x2) to: {OUTPUT_PREPARED}")
    print(f"Saved cluster assignments to: {OUTPUT_CSV}")
    print(f"Saved top keywords per cluster to: {OUTPUT_KEYWORDS}")
    print(f"Saved 2D scatter plot to: {OUTPUT_PLOT}")


if __name__ == "__main__":
    main()
