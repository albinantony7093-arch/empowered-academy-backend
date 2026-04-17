import os

# Absolute-safe base dir — works on Render, AWS, local regardless of cwd
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR  = os.path.dirname(BASE_DIR)          # backend/app/
DATA_DIR = os.path.join(APP_DIR, "data")


def data_path(filename: str) -> str:
    """Return an absolute path to a file inside backend/app/data/."""
    return os.path.join(DATA_DIR, filename)


# UG dataset  : NEET_UG_FINAL_INTEGRATED.json
# PG dataset  : NEET_PG_MASTER_FINAL.json   (name used in PG engine)
# Place both files in backend/app/data/ before deploying.
NEET_UG_DATA_PATH = data_path("NEET_UG_FINAL_INTEGRATED.json")
NEET_PG_DATA_PATH = data_path("NEET_PG_MASTER_FINAL.json")
