# scripts/weekly_summary.py
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv
import requests
from openai import OpenAI

ROOT = Path(".")
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "assets" / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

load_dotenv(override=True)

USE_OLLAMA = os.getenv("USE_OLLAMA", "true").lower() == "true"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct")

USE_OPENAI = os.getenv("USE_OPENAI", "false").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
openai_client = OpenAI(api_key=OPENAI_API_KEY) if (USE_OPENAI and OPENAI_API_KEY) else None

def load_pax():
    p = PROCESSED / "molinetes_2024_clean.parquet"
    if p.exists():
        df = pd.read_parquet(p)
        df["date"] = pd.to_datetime(df["date"])
        return df
    return None

def load_headway():
    p = PROCESSED / "headway_estimates_2024.csv"
    if p.exists():
        df = pd.read_csv(p)
        df["date"] = pd.to_datetime(df["year_month"] + "-01")
        return df
    return None

def ai_summarize(md: str, period: str) -> str:
    system = "Urban data analyst. Concise insights, bullet points, English only."
    user = f"Period: {period}\n\nData:\n{md}\n\nWrite 4-6 bullets and a short 'Next week' paragraph."

    if USE_OLLAMA:
        try:
            r = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": f"System: {system}\nUser: {user}", "stream": False, "options": {"temperature": 0.4}},
                timeout=120
            )
            r.raise_for_status()
            return r.json().get("response", "").strip()
        except Exception as e:
            return f"_(Ollama error: {e})_"
    elif openai_client:
        try:
            resp = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0.4,
                messages=[{"role":"system","content":system},{"role":"user","content":user}],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"_(OpenAI error: {e})_"
    else:
        return "- Stable week. Consider weather correlation.\n- Headway proxy consistent with dispatch volumes."

def main():
    dfp = load_pax()
    dfh = load_headway()
    if dfp is None:
        print("ERROR: passengers dataset not found.")
        return

    end = dfp["date"].max().normalize()
    start = end - timedelta(days=6)
    period = f"{start.date()} to {end.date()}"

    # filter window
    w = dfp[(dfp["date"]>=start) & (dfp["date"]<=end)]
    pax_by_line = w.groupby("line", observed=False)["passengers"].sum().sort_values(ascending=False)
    md = ["**Passengers (sum, last 7 days):**"]
    for line, val in pax_by_line.items():
        md.append(f"- {line}: {int(val):,}")

    if dfh is not None:
        hww = dfh[(dfh["date"]>=start) & (dfh["date"]<=end)]
        if not hww.empty and "avg_headway_min" in hww.columns:
            hw_by_line = hww.groupby("line", observed=False)["avg_headway_min"].mean().sort_values()
            md.append("\n**Avg. Headway (min, last 7 days):**")
            for line, val in hw_by_line.items():
                md.append(f"- {line}: {val:.2f} min")

    summary = ai_summarize("\n".join(md), period)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = REPORTS / f"weekly_summary_{ts}.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# Weekly Summary ({period})\n\n")
        f.write("\n".join(md))
        f.write("\n\n---\n\n")
        f.write(summary)
    print(f"Saved {out.as_posix()}")

if __name__ == "__main__":
    main()
