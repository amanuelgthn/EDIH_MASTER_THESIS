# === Build country-level, standardized matrix for clustering ===
# Requirements: pandas, scikit-learn
import pandas as pd
from sklearn.preprocessing import StandardScaler
from pathlib import Path

# ---------- USER CONFIG ----------
EXCEL_PATH = Path("combined_further_cleaned_keywords (1).xlsx")  # put your path here
HUB_SHEET = "Sheet1"
SERV_TOP5_SHEET = "services_Analysis"
SECT_TOP5_SHEET = "sectors_Analysis"
TECH_TOP5_SHEET = "technologies_Analysis"

# Advanced techs used for X3 (exact strings should match your normalized tokens)
ADVANCED_TECHS = {
    "artificial intelligence decision support",  # AI
    "internet of things",                        # IoT
    "digital twins",
    "high performance computing",
    "blockchain",
    "robotics",
}

# “Business/skills/ecosystem” services for X4 (feel free to expand to fit your taxonomy)
BUSINESS_SERVICES = {
    "sme support", "ecosystem building", "knowledge transfer", "skills development",
    "innovation management", "regional development", "funding support",
    "circular economy", "business development", "training"
}
# ---------------------------------

def parse_list(cell):
    """Split comma-separated tokens, lower-case, trim. Returns list[str]."""
    if pd.isna(cell):
        return []
    return [x.strip().lower() for x in str(cell).split(",") if x.strip()]

# Load sheets
df_hub = pd.read_excel(EXCEL_PATH, sheet_name=HUB_SHEET)
df_services = pd.read_excel(EXCEL_PATH, sheet_name=SERV_TOP5_SHEET)
df_sectors  = pd.read_excel(EXCEL_PATH, sheet_name=SECT_TOP5_SHEET)
df_tech     = pd.read_excel(EXCEL_PATH, sheet_name=TECH_TOP5_SHEET)

# Get Top-5 sets (first 5 rows of each analysis sheet)
top5_services = set(df_services.iloc[:5, 0].astype(str).str.lower())
top5_sectors  = set(df_sectors.iloc[:5, 0].astype(str).str.lower())
top5_techs    = set(df_tech.iloc[:5, 0].astype(str).str.lower())

# Build hub-level SST sets
hub_rows = []
for _, r in df_hub.iterrows():
    hub_rows.append({
        "country":   r.get("Country"),
        "sectors":   set(parse_list(r.get("Formatted sectors"))),
        "services":  set(parse_list(r.get("Formatted services"))),
        "techs":     set(parse_list(r.get("Formatted technologies"))),
    })

# Aggregate to country
country_stats = {}
for h in hub_rows:
    c = h["country"]
    if pd.isna(c): 
        continue
    country_stats.setdefault(c, {"n":0, "sectors": [], "services": [], "techs": []})
    country_stats[c]["n"] += 1
    country_stats[c]["sectors"].append(h["sectors"])
    country_stats[c]["services"].append(h["services"])
    country_stats[c]["techs"].append(h["techs"])

# Compute X1–X5
records = []
for country, st in country_stats.items():
    n = st["n"]
    all_sectors  = set().union(*st["sectors"])  if st["sectors"]  else set()
    all_services = set().union(*st["services"]) if st["services"] else set()
    all_techs    = set().union(*st["techs"])    if st["techs"]    else set()

    # X1: Breadth (average unique across SST)
    x1 = (len(all_sectors) + len(all_services) + len(all_techs)) / 3 if n > 0 else 0.0

    # X2: Top-5 concentration across SST
    top5_hits = len(all_sectors & top5_sectors) + len(all_services & top5_services) + len(all_techs & top5_techs)
    total_sst = len(all_sectors) + len(all_services) + len(all_techs)
    x2 = top5_hits / total_sst if total_sst else 0.0

    # X3: Advanced Tech Index
    adv_hits = len(all_techs & ADVANCED_TECHS)
    x3 = adv_hits / len(all_techs) if all_techs else 0.0

    # X4: ServiceMix Index (business/skills/ecosystem share)
    biz_hits = len(all_services & BUSINESS_SERVICES)
    x4 = biz_hits / len(all_services) if all_services else 0.0

    # X5: Distinctiveness (share outside Top-5 across SST)
    x5 = 1.0 - x2 if total_sst else 0.0

    records.append([country, n, x1, x2, x3, x4, x5])

df_country = pd.DataFrame(
    records,
    columns=["Country", "#EDIHs", "X1_Breadth", "X2_Top5_Concentration",
             "X3_Advanced_Tech_Index", "X4_ServiceMix_Index", "X5_Distinctiveness_Index"]
).sort_values("Country").reset_index(drop=True)

# Standardize X1–X5 (Ward requires standardized inputs)
feature_cols = ["X1_Breadth","X2_Top5_Concentration","X3_Advanced_Tech_Index","X4_ServiceMix_Index","X5_Distinctiveness_Index"]
scaler = StandardScaler()
df_std = df_country.copy()
df_std[feature_cols] = scaler.fit_transform(df_country[feature_cols])

# Save both raw and standardized tables (optional)
df_country.to_csv("country_features_raw.csv", index=False)
df_std.to_csv("country_features_standardized.csv", index=False)

print("Prepared tables:")
print(df_std.head())
