# 🧠 Urban Intelligence Lab

**Unified analytics and AI platform combining Subte-Dashboard and AI-Automation Workflow —  
where Business Intelligence meets Machine Learning for urban systems.**

---

## 🌆 Overview

Urban Intelligence Lab (UIL) is a living project that integrates **Business Intelligence**, **Automation**, and **Machine Learning** applied to urban data systems — starting with open data from Buenos Aires.

---

## 🧩 Stack

- Python 3.12  
- Dash + Plotly + Pandas  
- Streamlit  
- n8n + Ollama (local automation and LLMs)  
- SQLite / DuckDB

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

## 🚀 Status

**Week 1 – Unified Foundations:**  
Repository initialized, structure defined, and data integration in progress.


## 🗂 Data Layout & Sourcing

- Place **real open datasets** under `data/processed/`:
  - `molinetes_2024_clean.parquet` → passengers by line
  - `freq_from_form_2024.csv` or `formaciones_2024.parquet` → average headway (min)
- The app auto-detects columns with a small heuristic. If a metric is missing, it falls back to **DEMO**.
- Generate a tiny, consistent demo dataset anytime:
  ```bash
  python scripts/prepare_demo_data.py

## ▶️ Run (Local)

# activate venv, then:
python app/main_dashboard.py
# open http://127.0.0.1:8050
