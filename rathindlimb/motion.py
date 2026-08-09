"""Load motion data from MATLAB .mat files for TSL optimization."""

from itertools import product
from pathlib import Path

import numpy as np
import polars as pl
import scipy.io as sio

# Column names for the IK data in Control.mat.
# MATLAB string arrays can't be read by scipy.io, so these are hardcoded.
IK_COLUMNS = [
    "time",
    "sacrum_pitch",
    "sacrum_roll",
    "sacrum_yaw",
    "sacrum_x",
    "sacrum_y",
    "sacrum_z",
    "sacroiliac_r_flx",
    "hip_r_flx",
    "hip_r_add",
    "hip_r_int",
    "knee_r_flx",
    "ankle_r_flx",
    "ankle_r_add",
    "ankle_r_int",
    "sacroiliac_l_flx",
    "hip_l_flx",
    "hip_l_add",
    "hip_l_int",
    "knee_l_flx",
    "ankle_l_flx",
    "ankle_l_add",
    "ankle_l_int",
]

WALK_COORDS = ["hip_r_flx", "hip_r_add", "hip_r_int", "knee_r_flx", "ankle_r_flx"]


def load_walking_ik(
    mat_path: str | Path,
    coords: list[str] | None = None,
    n_std: float = 1.0,
    resolution: int = 2,
) -> pl.DataFrame:
    """
    Load walking IK data from Control.mat and return coordinate combinations.

    Extracts mean ± n_std standard deviations for each coordinate, then
    generates the Cartesian product across coordinates at each timestep.

    Parameters
    ----------
    mat_path : path to Control.mat
    coords : coordinate names to extract (default: WALK_COORDS)
    n_std : number of standard deviations for the range (default: 1.0)
    resolution : samples per coordinate per timestep (default: 2)
        Total combos per timestep = resolution ^ len(coords).
        1 = mean only (202 points), 2 = mean±1σ (6,464 points),
        3 = 3 evenly spaced (50,500 points).

    Returns
    -------
    Polars DataFrame with one column per coordinate, rows = timesteps × combos
    """
    if coords is None:
        coords = WALK_COORDS

    control = sio.loadmat(str(mat_path))
    phase = control["Timepoints"]["Baseline"][0, 0]["Phases"][0, 0]
    ik = phase["RightStanceSwing"][0, 0]["IK"][0, 0]

    avg = pl.DataFrame(ik["Average"][0, 0] * np.pi / 180, schema=IK_COLUMNS)
    std = pl.DataFrame(ik["StdDev"][0, 0] * np.pi / 180, schema=IK_COLUMNS)

    avg_coords = avg[coords]
    std_coords = std[coords]
    n_rows = avg_coords.shape[0]

    ub = avg_coords + n_std * std_coords
    lb = avg_coords - n_std * std_coords

    # linspace shape: (resolution, n_rows, n_coords)
    dist = np.linspace(lb.to_numpy(), ub.to_numpy(), resolution)
    # Cartesian product across coords at each timestep
    combos = np.array(
        [list(product(*dist[:, i, :].T)) for i in range(n_rows)]
    ).reshape(-1, len(coords))

    return pl.DataFrame(combos, schema=coords)
