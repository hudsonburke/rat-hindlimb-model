"""
# 04c TSL comparison

Merges TSL estimates from all sources into a single comparison table:
- Johnson 2011 (anatomical measurement)
- Eng 2008 (Lf/Lm ratio applied to model LMT)
- Optimized (Manal 2004 method, joint fiber-length + TSL)
"""

from pathlib import Path

import polars as pl

# %% Setup paths
project_root = Path.cwd().resolve().parent
data_dir = project_root / "data"

johnson_file = data_dir / "parameters" / "johnson_2011_parameters.csv"
eng_file = data_dir / "parameters" / "tsl_from_eng.csv"
optimized_file = data_dir / "parameters" / "tsl_comparison.csv"
output_csv = data_dir / "parameters" / "tsl_all_methods.csv"

# %% Load each source
johnson = pl.read_csv(johnson_file).select([
    pl.col("Abbreviation"),
    pl.col("l0 (mm)").alias("Johnson l0 (mm)"),
    pl.col("lts (mm)").alias("Johnson TSL (mm)"),
])

eng = pl.read_csv(eng_file).select([
    pl.col("Abbreviation"),
    pl.col("Lf/Lm").alias("Eng Lf/Lm"),
    pl.col("TSL from Eng (mm)"),
])

optimized = pl.read_csv(optimized_file)

# %% Merge on Abbreviation
comparison = (
    johnson
    .join(eng, on="Abbreviation", how="full", coalesce=True)
    .join(optimized, on="Abbreviation", how="full", coalesce=True)
    .sort("Abbreviation")
)

comparison.write_csv(output_csv)
print(f"Wrote {output_csv}")
print(comparison)
