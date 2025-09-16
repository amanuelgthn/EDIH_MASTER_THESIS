# clustering_ward_full_export.py
# ------------------------------------------------------------
# Runs Ward hierarchical clustering on standardized features,
# saves dendrogram (PNG), and exports rich analysis to Excel.
# ------------------------------------------------------------

import pandas as pd
import numpy as np
from pathlib import Path

# SciPy / plotting
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
from scipy.spatial.distance import pdist, squareform
from scipy.stats import f_oneway

# Matplotlib in headless mode (no GUI window)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Sklearn metrics
from sklearn.metrics import silhouette_samples, silhouette_score

# -------- USER CONFIG --------
STD_TABLE_PATH = Path("country_features_standardized.csv")
OUT_EXCEL = Path("clustering_outputs.xlsx")
OUT_DENDRO = Path("dendrogram_ward.png")
FEATURES = [
    "X1_Breadth",
    "X2_Top5_Concentration",
    "X3_Advanced_Tech_Index",
    "X4_ServiceMix_Index",
    "X5_Distinctiveness_Index",
]
K_LIST = [3, 4]
# -----------------------------

# Load standardized data
df = pd.read_csv(STD_TABLE_PATH)
countries = df["Country"].values
X = df[FEATURES].values

# Ward linkage on Euclidean distances
Z = linkage(X, method="ward")

# Save dendrogram as PNG (no window)
plt.figure(figsize=(14, 6))
dendrogram(
    Z,
    labels=countries,
    leaf_rotation=90,
    leaf_font_size=8,
)
plt.title("Hierarchical Clustering Dendrogram (Ward)")
plt.xlabel("Country")
plt.ylabel("Distance")
plt.tight_layout()
plt.savefig(OUT_DENDRO, dpi=200, bbox_inches="tight")
plt.close()
print(f"✅ Dendrogram saved to: {OUT_DENDRO.resolve()}")

# Attach cluster labels for requested K
for k in K_LIST:
    df[f"Cluster_{k}"] = fcluster(Z, k, criterion="maxclust")

# Helper: group members by cluster into a tidy table
def members_table(df_labels: pd.DataFrame, col: str) -> pd.DataFrame:
    rows = []
    for cl in sorted(df_labels[col].unique()):
        members = df_labels.loc[df_labels[col] == cl, "Country"].sort_values().tolist()
        for c in members:
            rows.append({"Cluster": cl, "Country": c})
    return pd.DataFrame(rows)

# Helper: cluster centroids (means of standardized features)
def centroids_table(df_labels: pd.DataFrame, col: str) -> pd.DataFrame:
    return df_labels.groupby(col)[FEATURES].mean().sort_index()

# Helper: counts per cluster
def counts_table(df_labels: pd.DataFrame, col: str) -> pd.DataFrame:
    vc = df_labels[col].value_counts().sort_index()
    return pd.DataFrame({"Cluster": vc.index, "Count": vc.values})

# Helper: WCSS (within-cluster sum of squares) for cohesion
def wcss_for_k(df_labels: pd.DataFrame, col: str) -> float:
    wcss = 0.0
    for cl in sorted(df_labels[col].unique()):
        Xi = df_labels.loc[df_labels[col] == cl, FEATURES].values
        mu = Xi.mean(axis=0, keepdims=True)
        wcss += float(((Xi - mu) ** 2).sum())
    return wcss

# Helper: ANOVA p-values per feature across clusters
def anova_table(df_labels: pd.DataFrame, col: str) -> pd.DataFrame:
    rows = []
    for feat in FEATURES:
        groups = [df_labels.loc[df_labels[col] == cl, feat].values
                  for cl in sorted(df_labels[col].unique())]
        # f_oneway requires at least 2 groups with data
        F, p = f_oneway(*groups)
        rows.append({"Feature": feat, "ANOVA_F": F, "p_value": p})
    out = pd.DataFrame(rows).sort_values("p_value")
    return out

# Silhouette (Euclidean) — overall & per-sample for each k
# We compute the full distance matrix once
D = squareform(pdist(X, metric="euclidean"))

silhouette_overall_rows = []
silhouette_by_country_sheets = {}

for k in K_LIST:
    labels = df[f"Cluster_{k}"].values
    # Overall silhouette
    try:
        sil_overall = silhouette_score(X, labels, metric="euclidean")
    except Exception:
        sil_overall = np.nan

    silhouette_overall_rows.append({"k": k, "silhouette_score": sil_overall})

    # Per-sample silhouette
    try:
        sil_samples = silhouette_samples(X, labels, metric="euclidean")
        sil_df = pd.DataFrame({
            "Country": countries,
            "Cluster": labels,
            "Silhouette": sil_samples
        }).sort_values(["Cluster", "Silhouette"], ascending=[True, False])
    except Exception:
        sil_df = pd.DataFrame({
            "Country": countries,
            "Cluster": labels,
            "Silhouette": np.nan
        })
    silhouette_by_country_sheets[k] = sil_df

# WCSS summary
wcss_rows = [{"k": k, "WCSS": wcss_for_k(df, f"Cluster_{k}")} for k in K_LIST]
wcss_df = pd.DataFrame(wcss_rows)

# Build and save Excel workbook with all outputs
with pd.ExcelWriter(OUT_EXCEL, engine="xlsxwriter") as writer:
    # Main table with features + labels
    df_out = df[["Country"] + FEATURES + [f"Cluster_{k}" for k in K_LIST]].sort_values("Country")
    df_out.to_excel(writer, sheet_name="Country_Clusters", index=False)

    # Counts, members, centroids, ANOVA, silhouettes
    # k = 3
    counts_table(df, "Cluster_3").to_excel(writer, sheet_name="Counts_k3", index=False)
    members_table(df, "Cluster_3").to_excel(writer, sheet_name="Members_k3", index=False)
    centroids_table(df, "Cluster_3").to_excel(writer, sheet_name="Centroids_k3")
    anova_table(df, "Cluster_3").to_excel(writer, sheet_name="ANOVA_k3", index=False)
    silhouette_by_country_sheets[3].to_excel(writer, sheet_name="Silhouette_k3_by_country", index=False)

    # k = 4
    counts_table(df, "Cluster_4").to_excel(writer, sheet_name="Counts_k4", index=False)
    members_table(df, "Cluster_4").to_excel(writer, sheet_name="Members_k4", index=False)
    centroids_table(df, "Cluster_4").to_excel(writer, sheet_name="Centroids_k4")
    anova_table(df, "Cluster_4").to_excel(writer, sheet_name="ANOVA_k4", index=False)
    silhouette_by_country_sheets[4].to_excel(writer, sheet_name="Silhouette_k4_by_country", index=False)

    # Overall silhouette + WCSS
    pd.DataFrame(silhouette_overall_rows).to_excel(writer, sheet_name="Silhouette", index=False)
    wcss_df.to_excel(writer, sheet_name="WCSS_k3_k4", index=False)

print(f"✅ Excel report saved to: {OUT_EXCEL.resolve()}")
