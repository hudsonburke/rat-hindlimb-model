from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from pathlib import Path

import numpy as np
import opensim as osim
import polars as pl
import scipy.io as sio
from osimpy.osim_graph import OsimGraph
from tsl_optimization import calc_tsl, optimize_fiber_length


DEFAULT_IK_COLUMNS = (
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
)

DEFAULT_WALK_COORDS = (
    "hip_r_flx",
    "hip_r_add",
    "hip_r_int",
    "knee_r_flx",
    "ankle_r_flx",
)


@dataclass(frozen=True)
class TslWorkflowConfig:
    ik_columns: tuple[str, ...] = DEFAULT_IK_COLUMNS
    walk_coords: tuple[str, ...] = DEFAULT_WALK_COORDS
    lm_norm_range: tuple[float, float] = (0.5, 1.5)
    lm_walk_range: tuple[float, float] = (0.6, 1.2)
    min_points: int = 100
    resolution: int = 1
    n_std: float = 1.0


@dataclass(frozen=True)
class MuscleTslResult:
    lmt_full: np.ndarray
    lm_opt: float
    lm: np.ndarray | float
    tsl: np.ndarray | float
    lmt_walk: np.ndarray
    lm_walk: np.ndarray | float
    tsl_walk: np.ndarray | float


def load_walk_coordinate_samples(
    control_path: str | Path,
    *,
    config: TslWorkflowConfig = TslWorkflowConfig(),
) -> pl.DataFrame:
    control = sio.loadmat(str(control_path))
    baseline_right_ik = control["Timepoints"]["Baseline"][0, 0]["Phases"][0, 0][
        "RightStanceSwing"
    ][0, 0]["IK"][0, 0]
    avg_right_ik = baseline_right_ik["Average"][0, 0] * np.pi / 180
    std_right_ik = baseline_right_ik["StdDev"][0, 0] * np.pi / 180

    avg_right_ik_df = pl.DataFrame(avg_right_ik, schema=list(config.ik_columns))
    std_right_ik_df = pl.DataFrame(std_right_ik, schema=list(config.ik_columns))

    avg_right_coords = avg_right_ik_df.select(config.walk_coords).to_numpy()
    std_right_coords = std_right_ik_df.select(config.walk_coords).to_numpy()

    upper_bound = avg_right_coords + config.n_std * std_right_coords
    lower_bound = avg_right_coords - config.n_std * std_right_coords
    dist = np.linspace(lower_bound, upper_bound, config.resolution)

    n_rows = avg_right_coords.shape[0]
    n_coords = len(config.walk_coords)
    n_combos = n_rows * (config.resolution**n_coords)
    coord_combos = np.array(
        [
            [*product(*dist[:, row_idx, :].T)]
            for row_idx in range(n_rows)
        ]
    ).reshape(n_combos, n_coords)
    return pl.DataFrame(coord_combos, schema=list(config.walk_coords))


def estimate_tsl_comparison(
    model_file: str | Path,
    control_file: str | Path,
    johnson_parameters_file: str | Path,
    *,
    config: TslWorkflowConfig = TslWorkflowConfig(),
    strict: bool = True,
) -> tuple[pl.DataFrame, dict[str, MuscleTslResult], dict[str, str]]:
    """Estimate both full-ROM and walking TSL tables.

    Downstream model updates should use the walking-derived values. The full-ROM column is retained as a diagnostic comparison because Cartesian combinations of joint limits can produce physiologically unreachable muscle-tendon lengths.
    """
    graph = OsimGraph.from_file(str(model_file))
    walk_df = load_walk_coordinate_samples(control_file, config=config)

    results_full = graph.get_all_muscle_lengths_rom(min_points=config.min_points)
    muscle_names = list(results_full)
    lengths_walk = graph.get_muscle_lengths_from_data(muscle_names, walk_df)

    johnson_params = pl.read_csv(johnson_parameters_file)
    johnson_tsl_mm = dict(
        zip(
            johnson_params.get_column("Abbreviation").to_list(),
            johnson_params.get_column("lts (mm)").to_list(),
            strict=True,
        )
    )

    tsl_rows: list[dict[str, float | str | None]] = []
    tsl_results: dict[str, MuscleTslResult] = {}
    failures: dict[str, str] = {}
    for muscle_name, lmt in results_full.items():
        try:
            result = _estimate_muscle_tsl(
                graph,
                muscle_name,
                lmt,
                lengths_walk,
                config=config,
            )
        except Exception as exc:  # noqa: BLE001
            if strict:
                raise RuntimeError(f"Failed tendon slack estimation for {muscle_name}") from exc
            failures[muscle_name] = str(exc)
            continue

        tsl_results[muscle_name] = result
        abbrev = muscle_name.split("_", 1)[1] if "_" in muscle_name else muscle_name
        tsl_rows.append(
            {
                "Abbreviation": abbrev,
                "Johnson TSL (mm)": johnson_tsl_mm.get(abbrev),
                "Full ROM TSL (mm)": float(np.mean(np.asarray(result.tsl))) * 1000,
                "Walk TSL (mm)": float(np.mean(np.asarray(result.tsl_walk))) * 1000,
            }
        )

    tsl_df = pl.DataFrame(tsl_rows).sort("Abbreviation")
    return tsl_df, tsl_results, failures


def write_tsl_comparison(output_file: str | Path, tsl_df: pl.DataFrame) -> Path:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tsl_df.write_csv(output_path)
    return output_path


def _estimate_muscle_tsl(
    graph: OsimGraph,
    muscle_name: str,
    lmt_full_df: pl.DataFrame,
    lengths_walk: pl.DataFrame,
    *,
    config: TslWorkflowConfig,
) -> MuscleTslResult:
    muscle: osim.Muscle = graph.get_muscle(muscle_name)
    lm_opt = float(muscle.get_optimal_fiber_length())
    alpha_opt = float(muscle.get_pennation_angle_at_optimal())

    millard: osim.Millard2012EquilibriumMuscle = osim.Millard2012EquilibriumMuscle.safeDownCast(
        muscle
    )
    afl = millard.getActiveForceLengthCurve()
    pfl = millard.getFiberForceLengthCurve()
    tfl = millard.getTendonForceLengthCurve()

    lmt_full = _sorted_unique_lengths(lmt_full_df, muscle_name)
    lm = optimize_fiber_length(
        lmt_full,
        lm_opt,
        alpha_opt,
        afl,
        pfl,
        tfl,
        config.lm_norm_range,
    )
    tsl = calc_tsl(lmt_full, lm, lm_opt, alpha_opt, afl, pfl, tfl)

    lmt_walk = _sorted_unique_lengths(lengths_walk, muscle_name)
    lm_walk = optimize_fiber_length(
        lmt_walk,
        lm_opt,
        alpha_opt,
        afl,
        pfl,
        tfl,
        config.lm_walk_range,
    )
    tsl_walk = calc_tsl(lmt_walk, lm_walk, lm_opt, alpha_opt, afl, pfl, tfl)

    return MuscleTslResult(
        lmt_full=lmt_full,
        lm_opt=lm_opt,
        lm=lm,
        tsl=tsl,
        lmt_walk=lmt_walk,
        lm_walk=lm_walk,
        tsl_walk=tsl_walk,
    )


def _sorted_unique_lengths(length_df: pl.DataFrame, muscle_name: str) -> np.ndarray:
    lengths = length_df.get_column(muscle_name).to_numpy()
    return np.clip(np.sort(np.unique(lengths)), 1.0e-6, None)
