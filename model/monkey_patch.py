import builtins
import pandas as pd
from collections import Counter
import atexit
import os

# keep counters
_imported_csvs = Counter()

# --- patch pandas.read_csv ---
_original_read_csv = pd.read_csv

def logging_read_csv(filepath, *args, **kwargs):
    filepath = str(filepath)
    if not filepath.lower().startswith("output"):   # <-- skip output files
        _imported_csvs[filepath] += 1
        # print(f"[INFO] Importing CSV via pandas: {filepath} (count: {_imported_csvs[filepath]})")
    return _original_read_csv(filepath, *args, **kwargs)

pd.read_csv = logging_read_csv

# --- patch builtins.open ---
_original_open = builtins.open

def logging_open(filepath, *args, **kwargs):
    if isinstance(filepath, (str, bytes, os.PathLike)):
        filepath_str = str(filepath)
        if filepath_str.lower().endswith(".csv") and not filepath_str.lower().startswith("output"):
            _imported_csvs[filepath_str] += 1
            # print(f"[INFO] Opening CSV via open(): {filepath_str} (count: {_imported_csvs[filepath_str]})")
    return _original_open(filepath, *args, **kwargs)

builtins.open = logging_open

# --- print summary at exit ---
@atexit.register
def report_csvs():
    print("\n--- CSV files imported during run ---")
    for f, count in _imported_csvs.items():
        # print(f"{f}  →  {count} times")
        print(f"{f}")
