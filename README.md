# EDIH_MASTER_THESIS

This repository contains the codebase for my Master's thesis research on **EDIH Ecosystem Analysis**, focusing on **sectors, services, and technologies (SST)**.  
It supports the data pipeline from **web scraping → cleaning → post-processing → matrix generation → clustering analysis**, forming the computational foundation that complements the thesis.

---

## 📂 Folders

### `SST_Matrix/`
Contains scripts and outputs for **SST matrix generation**:
- Builds pairwise and 3D co-occurrence matrices (Sector × Service × Technology).
- Produces annotated heatmaps for Top-K slices.  

👉 See [SST_Matrix/README.md](./SST_Matrix/README.md) for details.

---

### `Clustering/`
Implements clustering methodologies (mainly hierarchical) on hubs and countries.  
Includes:
- **`heirarchical/`** → final clustering pipeline.  
- **`Clustering_Legacy_Archive/`** → earlier clustering experiments.  
- **Outputs:** Excel cluster reports, dendrograms, standardized datasets.  

👉 Each subfolder has its own documentation.

---

### `Post_Scraping/`
Holds **post-processed Excel files** (e.g., `combined_further_cleaned_keywords.xlsx`) and scripts for refining scraped data.  
Used as the bridge between scraping and matrix generation.  

👉 Separate README provides instructions.

---

### `thesis/`
This folder contains the **Python virtual environment** used in the project.  
Before running any scripts, you should activate it:

- On **Linux/Mac**:
  ```bash
  source thesis/bin/activate
On Windows (PowerShell):

### powershell

thesis\Scripts\activate
This ensures the correct package versions are loaded for reproducibility.

## Workflow
mermaid

flowchart LR
    A[CategoryScraper.py] --> B[CleanData.py]
    B --> C[Post_Scraping/]
    C --> D[SST_Matrix/]
    D --> E[Clustering/]
    E --> F[Final Outputs: Reports, Heatmaps, Clusters]
## 🚀 Usage
## 1. Clone the repository

 ```bash
  git clone https://github.com/amanueltghn/EDIH_MASTER_THESIS.git
 cd EDIH_MASTER_THESIS```

## 2. Activate the environment (recommended):

#### Linux/Mac:

 ```bash
  source thesis/bin/activate```
Windows:

#### powershell
 ```bash
thesis\Scripts\activate```

## 3.Install dependencies
If not already included in the environment:

 ```bash
  pip install -r requirements.txt```

## 4.Run scripts as needed

Scraping:

 ```bash
  python CategoryScraper.py```

Cleaning:

 ```bash
  python CleanData.py```
End-to-end pipeline:

 ```bash
  python main.py```
📖 Documentation
Each major folder (SST_Matrix, Clustering, Post_Scraping) has or will have its own README with detailed instructions.
This main README provides a high-level overview of how the pieces fit together.

