# EDIH_MASTER_THESIS
Python repository for EDIH Ecosystem Analysis, focusing on sectors, services, and technologies.

flowchart TD
  %% Phase labels
  subgraph Phase1 [Phase 1 – Observation & Conceptualization]
    L1[1. Literature & Policy Scan<br/>• EC DIH catalogues<br/>• D-BEST, DR-BEST, etc.]
    L2[2. Industrial Requirements Harvesting<br/>• Interviews with 5–8 EDIH coordinators<br/>• Policy calls & docs]
    L3[3. Initial SST Framework Sketch<br/>• 3-level taxonomy draft]
  end

  subgraph Phase2 [Phase 2 – Theory & Tool Development]
    M1[1. Data Acquisition & Filtering<br/>• EC portal scraping/API]
    M2[2. Data Cleaning & Normalization<br/>• Harmonize labels, geocode]
    M3[3. Taxonomy Instantiation<br/>• Assign offerings → Level 1/2/3 classes]
    M4[4. Analytical Procedures<br/>• Clustering, gap‐mapping]
    M5[5. Proof-of-Concept Dashboard<br/>• Shiny/Dash interface]
  end

  subgraph Phase3 [Phase 3 – Validation & Refinement]
    N1[1. Expert Review<br/>• Panel of 10 EDIH reps + 5 policymakers]
    N2[2. Benchmarking<br/>• Compare vs. D-BEST, DR-BEST]
    N3[3. Iterative Refinement<br/>• Update taxonomy & dashboard]
    N4[4. Final Assessment<br/>• SUS survey of 50 users]
  end

  %% Flow arrows
  L1 --> L2 --> L3 --> M1
  M1 --> M2 --> M3 --> M4 --> M5 --> N1
  N1 --> N2 --> N3 --> N4
