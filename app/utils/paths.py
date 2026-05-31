import os

# Absolute-safe base dir — works on Render, AWS, local regardless of cwd
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR  = os.path.dirname(BASE_DIR)          # backend/app/
DATA_DIR = os.path.join(APP_DIR, "data")


def data_path(filename: str) -> str:
    """Return an absolute path to a file inside backend/app/data/."""
    return os.path.join(DATA_DIR, filename)


# All 5 courses currently share one question set.
# Swap individual paths later when separate datasets are ready.
SHARED_DATA_PATH = data_path("NEET_MCQ_Clean_5227_v5_Final .json")

NEET_UG_DATA_PATH    = SHARED_DATA_PATH
NEET_PG_DATA_PATH    = SHARED_DATA_PATH
NEET_CRASH_DATA_PATH = SHARED_DATA_PATH
