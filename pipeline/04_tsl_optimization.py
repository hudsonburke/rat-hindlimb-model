"""
# 04 TSL Optimization

Estimate tendon slack lengths from muscle fiber lengths observed during
walking. Uses the Manal & Buchanan (2004) method via the tsl-optimization
package.

Requires the unilateral model from step 02 and walking motion data.
"""

from pathlib import Path

from osimpy.osim_graph import OsimGraph
from rathindlimb.motion import load_walking_ik
from rathindlimb.tsl import optimize_tsl_for_model

# %% Setup paths
project_root = Path.cwd().resolve().parent
output_dir = project_root / "models" / "output"
data_dir = project_root / "data"

model_file = output_dir / "rat_hindlimb_unilateral.osim"
motion_file = data_dir / "motion" / "Control.mat"
output_csv = data_dir / "parameters" / "tsl_comparison.csv"

# %% Load model and motion data
graph = OsimGraph.from_file(str(model_file))
walk_data = load_walking_ik(motion_file, resolution=2)

# %% Run optimization (walking ROM only — faster and more physically relevant)
tsl_df = optimize_tsl_for_model(
    graph,
    walk_data=walk_data,
    lm_walk_range=(0.6, 1.5),
    max_evaluations=2000,
    timeout_seconds=60,
    n_walk_timesteps=202,
)

# %% Save results
tsl_df.write_csv(output_csv)
print(f"Wrote {output_csv}")
print(tsl_df)
