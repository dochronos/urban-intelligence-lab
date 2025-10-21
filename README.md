# 🧠 Urban Intelligence Lab

> “Where Business Intelligence meets Machine Learning for urban systems.”

Urban Intelligence Lab is the unified evolution of two complementary projects —  
**Subte-Dashboard** (urban BI platform) and **AI-Automation Workflow** (AI-based automation pipeline).  
It combines analytics, automation, and AI models into one living portfolio project focused on **urban systems** such as public transport, mobility, and energy.

---

## 🌆 Overview

- **Objective:** create an open, modular laboratory where Business Intelligence meets Machine Learning.  
- **Context:** the project merges real open data from Buenos Aires with AI-driven insights.  
- **Focus Areas:** analytics, automation, and prediction applied to real-world city data.  
- **Data Sources:** open datasets from Buenos Aires Subte (metro system).

---

## 🧱 Tech Stack

| Layer | Technologies |
|-------|---------------|
| BI & Visualization | Dash · Plotly · Pandas |
| Automation | n8n |
| AI & Insights | Streamlit · Ollama (local LLM) |
| Data Storage | SQLite · DuckDB · Parquet |
| Environment | Python 3.12 · Virtualenv |

---

## 📁 Structure

urban-intelligence-lab/
├── app/ # Dash/Streamlit apps
├── data/
│ ├── raw/ # Raw open data
│ └── processed/ # Cleaned datasets
├── notebooks/ # ETL and analysis
├── scripts/ # Reusable scripts
├── assets/
│ └── screenshots/ # Visual assets for posts
├── README.md
└── requirements.txt

---

## 📊 Datasets Used

| File | Description | Source |
|------|--------------|--------|
| `molinetes_2024_clean.parquet` | Passengers by line | Subte open data |
| `freq_from_form_2024.csv` | Monthly dispatched trains | Derived from Subte data |
| `formaciones_2024.parquet` | Daily train formations | Subte open data |
| `headway_estimates_2024.csv` | Estimated headway (min) | Generated via ETL script |

---

## ⚙️ ETL and Processing

**Headway estimation formula:**

avg_headway_min = (OPERATING_MIN_PER_DAY * days_in_month) / dispatched_trains

OPERATING_MIN_PER_DAY = 1080 (18 operational hours)

Derived in scripts/etl_headway_from_formaciones.py

Output → data/processed/headway_estimates_2024.csv

python scripts/etl_headway_from_formaciones.py

---

## 🚀 Status

**Week 1 – Unified Foundations:**  
Repository initialized, structure defined, and data integration in progress.


## 🗂 Data Layout & Sourcing

- Place **real open datasets** under `data/processed/`:
  - `molinetes_2024_clean.parquet` → passengers by line
  - `freq_from_form_2024.csv` or `formaciones_2024.parquet` → average headway (min)
- The app auto-detects columns with a small heuristic. If a metric is missing, it falls back to **DEMO**.
- Generate a tiny, consistent demo dataset anytime:
  python scripts/prepare_demo_data.py

## ▶️ Run (Local)

# activate venv, then:
python app/main_dashboard.py
# open http://127.0.0.1:8050

## 🧪 Headway Estimates (Week 1)

We don’t have native headway fields in source data, so we derive **avg_headway_min** using a transparent proxy:

- From `freq_from_form_2024.csv` (monthly): `avg_headway_min = (OPERATING_MIN_PER_DAY * days_in_month) / dispatched_trains`
- Fallback: from `formaciones_2024.parquet` (daily → monthly aggregation)

Assumptions:
- `OPERATING_MIN_PER_DAY = 1080` (18h/day). Adjust in `scripts/etl_headway_from_formaciones.py`.

---

## 🚀 Week 1 – Unified Foundations

Highlights:

Created base repository and folder structure

Connected real passenger and service datasets

Built first Dash visualization

Derived and visualized Average Headway (min)

Generated reproducible screenshot assets

Next Steps (Weeks 2–3):

Integrate AI-driven insights via Streamlit + Ollama

Automate ETL and dashboard updates via n8n

Expand data sources (GTFS, climate, mobility)

## 🧩 License & Credits

Open data © Gobierno de la Ciudad de Buenos Aires
Developed by Herman Schubert as part of the Professional Developer & Full Stack certification projects.
