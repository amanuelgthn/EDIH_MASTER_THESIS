import pandas as pd
import re

# === INPUTS ===
HUB_FILE = "combined_further_cleaned_keywords (1).xlsx"   # hub-level SST data
CLUSTER_FILE = "Country_clusters_hier_k2_k6_ENTROPY.xlsx"         # clustering results
OUTPUT_FILE = "Cluster_Report_entropy.xlsx"                       # output report

# Column names in hub data
SECTOR_COL  = "Formatted sectors"
SERVICE_COL = "Formatted services"
TECH_COL    = "Formatted technologies"
COUNTRY_COL = "Country"
TITLE_COL   = "EDIH Titlels"   # adjust if your file uses another column name for hub titles

# Load hub-level SST data
df_hubs = pd.read_excel(HUB_FILE)

# Load cluster labels (adjust sheet name depending on method/k you want)
labels = pd.read_excel(CLUSTER_FILE, sheet_name="Labels_Ward_k4")  # or Labels_CosineAvg_k4
df = df_hubs.merge(labels[["Country", "Ward_k4"]], on="Country", how="left")
df = df.rename(columns={"Ward_k4": "Cluster"})

# Helper: split multi-value cells
def split_multi(val):
    if pd.isna(val):
        return []
    return [re.sub(r"\s+", " ", s.strip()) for s in re.split(r"[;,|]", str(val)) if s.strip()]

for col in [SECTOR_COL, SERVICE_COL, TECH_COL]:
    df[col] = df[col].apply(split_multi)

# === 4.X.2 Cluster Sizes ===
cluster_sizes = df.groupby("Cluster")[TITLE_COL].count().reset_index()
cluster_sizes = cluster_sizes.rename(columns={TITLE_COL: "# Hubs"})

# === 4.X.3 Cluster Profiles (Top 5) ===
def top_n(series, n=5):
    flat = [x for sub in series for x in sub]
    return "; ".join(pd.Series(flat).value_counts().head(n).index)

profiles = []
for c, g in df.groupby("Cluster"):
    profiles.append({
        "Cluster": c,
        "Top Sectors": top_n(g[SECTOR_COL], n=5),
        "Top Services": top_n(g[SERVICE_COL], n=5),
        "Top Technologies": top_n(g[TECH_COL], n=5)
    })
profiles = pd.DataFrame(profiles)

# === 4.X.6 Membership by Country (with sample hubs) ===
membership = []
for c, g in df.groupby("Cluster"):
    hubs = g[TITLE_COL].dropna().unique().tolist()
    membership.append({
        "Cluster": c,
        "# Hubs": len(g),
        "Countries (sample)": ", ".join(g[COUNTRY_COL].unique()[:5]),  # sample first 5
        "Example Hubs": "; ".join(hubs[:5])  # sample first 5 hubs
    })
membership = pd.DataFrame(membership)

# === Write all tables to Excel ===
with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
    cluster_sizes.to_excel(writer, sheet_name="Cluster_Sizes", index=False)
    profiles.to_excel(writer, sheet_name="Cluster_Profiles_Top5", index=False)
    membership.to_excel(writer, sheet_name="Cluster_Membership", index=False)

print(f"✅ Saved cluster report to {OUTPUT_FILE}")
