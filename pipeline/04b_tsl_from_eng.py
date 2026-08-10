"""
# 04b TSL from Eng 2008 ratios

Estimates tendon slack length using Eng et al. (2008) fiber-length to
muscle-length ratios (Lf/Lm) applied to the model's muscle-tendon lengths.

TSL = LMT × (1 - Lf/Lm)

This is a simple geometric estimate — no optimization involved.
"""

from pathlib import Path

import numpy as np
import polars as pl
from osimpy.osim_graph import OsimGraph

# %% Setup paths
project_root = Path.cwd().resolve().parent
output_dir = project_root / "models" / "output"
data_dir = project_root / "data"

model_file = output_dir / "rat_hindlimb_unilateral.osim"
eng_file = data_dir / "parameters" / "eng_2008_parameters.csv"
output_csv = data_dir / "parameters" / "tsl_from_eng.csv"

# %% Load model and Eng data
graph = OsimGraph.from_file(str(model_file))
state = graph.osim_model.initSystem()
eng = pl.read_csv(eng_file)

# %% Compute TSL for each muscle with Eng data
rows = []
for muscle_name in graph.get_muscle_names():
    muscle = graph.get_muscle(muscle_name)
    lmt = float(muscle.getLength(state)) * 1000  # m -> mm
    abbrev = muscle_name.split("R_")[-1] if "R_" in muscle_name else muscle_name

    row = eng.filter(pl.col("Abbreviation") == abbrev)
    if len(row) == 0 or "Lf/Lm" not in row.columns:
        continue

    lflm = row["Lf/Lm"][0]
    if lflm is None or not np.isfinite(lflm) or lflm <= 0:
        continue

    tsl = lmt * (1 - lflm)
    rows.append({"Abbreviation": abbrev, "LMT (mm)": lmt, "Lf/Lm": lflm, "TSL from Eng (mm)": tsl})

tsl_df = pl.DataFrame(rows).sort("Abbreviation")
tsl_df.write_csv(output_csv)
print(f"Wrote {output_csv}")
print(tsl_df)
