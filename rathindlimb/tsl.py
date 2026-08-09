"""Tendon slack length optimization for an OpenSim model."""

import signal
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import opensim as osim
import polars as pl
from osimpy.osim_graph import OsimGraph
from tsl_optimization import calc_tsl, optimize_fiber_length


@contextmanager
def _timeout(seconds: int, muscle_name: str):
    """Raise TimeoutError after `seconds` (Unix only)."""

    def _handler(signum, frame):
        raise TimeoutError(f"{muscle_name} optimization timed out after {seconds}s")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def _extract_curves(muscle: osim.Muscle):
    """Extract OpenSim force-length curves from a Millard muscle."""
    millard = osim.Millard2012EquilibriumMuscle.safeDownCast(muscle)
    return (
        millard.getActiveForceLengthCurve(),
        millard.getFiberForceLengthCurve(),
        millard.getTendonForceLengthCurve(),
    )


def _optimize_single(
    lmt: np.ndarray,
    lm_opt: float,
    alpha_opt: float,
    afl,
    pfl,
    tfl,
    lm_norm_range: tuple[float, float],
    max_evaluations: int = 5000,
) -> float | None:
    """Run fiber-length optimization and return mean TSL in mm, or None on failure."""
    try:
        lm = optimize_fiber_length(
            lmt, lm_opt, alpha_opt, afl, pfl, tfl,
            lm_norm_range, max_evaluations=max_evaluations,
        )
        tsl = calc_tsl(lmt, lm, lm_opt, alpha_opt, afl, pfl, tfl)
        return float(np.mean(tsl)) * 1000
    except RuntimeError:
        return None


def optimize_tsl_for_model(
    graph: OsimGraph,
    walk_data: pl.DataFrame | None = None,
    lm_norm_range: tuple[float, float] = (0.5, 1.5),
    lm_walk_range: tuple[float, float] = (0.6, 1.2),
    min_points: int = 50,
    max_evaluations: int = 5000,
    timeout_seconds: int = 30,
) -> pl.DataFrame:
    """
    Optimize tendon slack lengths for all muscles in the model.

    If walk_data is provided, only the walking ROM is optimized (faster,
    more physically relevant). Otherwise, the full joint ROM is used.

    Parameters
    ----------
    graph : OsimGraph loaded from the model
    walk_data : DataFrame with walking coordinate data (optional)
    lm_norm_range : normalized fiber length range for full ROM
    lm_walk_range : normalized fiber length range for walking
    min_points : minimum sample points for full ROM evaluation
    max_evaluations : max optimizer iterations per muscle
    timeout_seconds : per-muscle timeout (Unix only)

    Returns
    -------
    DataFrame with columns: Abbreviation, TSL (mm)
    """
    walk_lengths = None
    if walk_data is not None:
        print("Getting walk lengths...")
        walk_lengths = graph.get_muscle_lengths_from_data(
            graph.get_muscle_names(), walk_data
        )
        print("Got walk lengths")
    else:
        print("Getting full ROM lengths...")
        full_rom_lengths = graph.get_all_muscle_lengths_rom(min_points=min_points)
        print("Got full ROM lengths")

    muscles = graph.get_muscle_names()
    rows = []

    for idx, muscle_name in enumerate(muscles):
        print(f"  [{idx+1}/{len(muscles)}] {muscle_name}...", end=" ", flush=True)

        muscle = graph.get_muscle(muscle_name)
        lm_opt = float(muscle.get_optimal_fiber_length())
        alpha_opt = float(muscle.get_pennation_angle_at_optimal())
        afl, pfl, tfl = _extract_curves(muscle)
        abbrev = muscle_name.split("R_")[-1] if "R_" in muscle_name else muscle_name

        # Determine which data source to use
        if walk_lengths is not None:
            lmt_raw = walk_lengths.select(muscle_name).to_numpy()
            norm_range = lm_walk_range
        else:
            lmt_raw = full_rom_lengths[muscle_name].to_numpy()
            norm_range = lm_norm_range

        lmt = np.clip(np.sort(np.unique(lmt_raw)), 1e-6, None)

        with _timeout(timeout_seconds, muscle_name):
            tsl_val = _optimize_single(
                lmt, lm_opt, alpha_opt, afl, pfl, tfl,
                norm_range, max_evaluations,
            )

        if tsl_val is not None:
            print(f"{tsl_val:.2f}mm", flush=True)
        else:
            print("FAILED", flush=True)

        row = {"Abbreviation": abbrev}
        if walk_lengths is not None:
            row["Walk TSL (mm)"] = tsl_val
        else:
            row["Full ROM TSL (mm)"] = tsl_val
        rows.append(row)

    return pl.DataFrame(rows).sort("Abbreviation")
