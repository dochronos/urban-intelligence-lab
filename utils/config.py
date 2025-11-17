from pathlib import Path

# Project root: /.../urban-intelligence-lab
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Default data folders
DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"
