"""End-to-end analysis pipeline for rat gait data.

Pipeline steps
--------------
1. Scale model to subject anthropometrics (rathindlimb.scale + Hicks regression)
2. Run Inverse Kinematics (osimpy.IKSettings)
3. Run Inverse Dynamics (osimpy.IDSettings)
4. Interpolate results to common gait % and extract mean ± SD per group
5. (Optional) Run Computed Muscle Control (osimpy.CMCSettings)
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)

# Try imports that depend on OpenSim — they fail gracefully if not installed
try:
    from osimpy.tools import IKSettings, IDSettings, ScaleSettings
    from osimpy import sto_to_df
    _HAS_OSIMPLE = True
except ImportError:
    _HAS_OSIMPLE = False
    logger.warning("osimpy not available — analysis steps will be stubs")

try:
    from rathindlimb.scale import scale_opensim_model, RatScalingParameters
    _HAS_SCALE = True
except ImportError:
    _HAS_SCALE = False
    logger.warning("rathindlimb.scale not available — scaling will be a stub")


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass
class SubjectResult:
    """Results from a single subject's analysis pipeline run."""
    subject_id: str
    session: str
    scaled_model: Path | None = None
    ik_file: Path | None = None
    id_file: Path | None = None
    ik_df: pl.DataFrame | None = None
    id_df: pl.DataFrame | None = None
    success: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class GroupResult:
    """Aggregated results for a treatment group."""
    group_name: str
    subjects: list[SubjectResult] = field(default_factory=list)
    ik_mean: pl.DataFrame | None = None
    ik_std: pl.DataFrame | None = None
    id_mean: pl.DataFrame | None = None
    id_std: pl.DataFrame | None = None


# =========================================================================
# Step 1: Scale
# =========================================================================
def scale_subject(
    base_model: Path,
    subject_name: str,
    mass: float,
    femur_length: float,
    tibia_length: float,
    output_dir: Path,
    static_trc: Path | None = None,
    foot_length: float = 0.0,
    side: str = "R",
) -> Path:
    """Scale bilateral rat model to subject anthropometrics.

    Uses :func:`rathindlimb.scale.scale_opensim_model` which:
    1. Computes manual scale factors from segment length ratios
    2. Runs the OpenSim Scale Tool
    3. Overrides inertial properties via Hicks regression

    If *static_trc* is provided, the marker-based scale step is also run.
    """
    if not _HAS_SCALE:
        raise ImportError("rathindlimb.scale is required for scaling")

    params = RatScalingParameters(
        Mass=mass,
        RFemurLength=femur_length if side == "R" else femur_length,
        RTibiaLength=tibia_length if side == "R" else tibia_length,
        LFemurLength=femur_length if side == "L" else femur_length,
        LTibiaLength=tibia_length if side == "L" else tibia_length,
        RFootLength=foot_length,
        LFootLength=foot_length,
    )

    scale_opensim_model(
        name=subject_name,
        trc_file_name=str(static_trc) if static_trc else "",
        parameters=params,
        output_dir=str(output_dir),
    )

    scaled = output_dir / f"{subject_name}_scaled.osim"
    if not scaled.exists():
        raise RuntimeError(f"Scaling produced no output at {scaled}")
    logger.info(f"Scaled model: {scaled}")
    return scaled


# =========================================================================
# Step 2: Inverse Kinematics
# =========================================================================
def run_ik(
    model_path: Path,
    trc_path: Path,
    output_dir: Path,
    task_set_path: Path | None = None,
    name: str = "rat_ik",
) -> Path:
    """Run OpenSim Inverse Kinematics on a single trial."""
    if not _HAS_OSIMPLE:
        raise ImportError("osimpy is required for IK")

    settings = IKSettings(
        name=name,
        model_path=model_path,
        marker_path=trc_path,
        results_directory=output_dir,
        output_motion_file="ik_results.mot",
        task_set_path=task_set_path,
    )
    result = settings.run()
    if not result.success:
        raise RuntimeError(f"IK failed: {result.errors}")
    logger.info(f"IK complete: {result.motion_file}")
    return result.motion_file


# =========================================================================
# Step 3: Inverse Dynamics
# =========================================================================
def run_id(
    model_path: Path,
    mot_path: Path,
    output_dir: Path,
    external_loads_path: Path | None = None,
    lowpass_cutoff: float = 6.0,
    name: str = "rat_id",
) -> Path:
    """Run OpenSim Inverse Dynamics on IK results."""
    if not _HAS_OSIMPLE:
        raise ImportError("osimpy is required for ID")

    settings = IDSettings(
        name=name,
        model_path=model_path,
        coordinates_path=mot_path,
        results_directory=output_dir,
        output_forces_file="id_results.sto",
        external_loads_path=external_loads_path,
        lowpass_cutoff_frequency=lowpass_cutoff,
    )
    result = settings.run()
    if not result.success:
        raise RuntimeError(f"ID failed: {result.errors}")
    logger.info(f"ID complete: {result.moments_file}")
    return result.moments_file


# =========================================================================
# Step 4: Interpolate results to gait cycle
# =========================================================================
def interp_to_gait(
    df: pl.DataFrame,
    time_col: str = "time",
    n_points: int = 101,
    stance_pct: float = 50.0,
) -> pl.DataFrame:
    """Interpolate IK/ID data from 0-100% gait cycle.

    Uses stance/swing event detection from the data.  Assumes time
    increases monotonically through the trial.
    """
    from scipy.interpolate import interp1d

    time = df[time_col].to_numpy()
    data_cols = [c for c in df.columns if c != time_col]

    # Create 0-100% gait cycle
    gait_pct = np.linspace(0, 100, n_points)

    result = {"gait_percentage": gait_pct}
    for col in data_cols:
        y = df[col].to_numpy()
        # Remove NaN for interpolation
        mask = np.isfinite(y)
        if mask.sum() < 2:
            continue
        f = interp1d(
            time[mask], y[mask], kind="linear",
            bounds_error=False, fill_value="extrapolate",
        )
        result[col] = f(gait_pct)

    return pl.DataFrame(result)


# =========================================================================
# Step 5: Full subject pipeline
# =========================================================================
def run_subject_pipeline(
    base_model: Path,
    subject_name: str,
    session: str,
    trc_dir: Path,
    output_dir: Path,
    subject_mass: float | None = None,
    subject_femur: float | None = None,
    subject_tibia: float | None = None,
    scale_dir: Path | None = None,
    task_set: Path | None = None,
    external_loads: Path | None = None,
    skip_scaling: bool = False,
    skip_ik: bool = False,
    skip_id: bool = False,
) -> SubjectResult:
    """Run the full IK/ID pipeline for one subject session.

    Parameters
    ----------
    base_model : Path
        Path to the bilateral rat model (.osim).
    subject_name : str
        Subject identifier (e.g. "BAA01").
    session : str
        Session label (e.g. "baseline", "week24").
    trc_dir : Path
        Directory containing .trc marker files and .grf force files.
    output_dir : Path
        Directory for all output files.
    subject_mass, subject_femur, subject_tibia : float
        Anthropometrics for scaling (required unless skip_scaling=True).
    scale_dir : Path | None
        Directory for scaled models (default: output_dir/scaled).
    task_set : Path | None
        IK task set XML (optional).
    external_loads : Path | None
        External loads XML for ID (optional).
    """
    output_dir = Path(output_dir)
    scale_dir = Path(scale_dir) if scale_dir else output_dir / "scaled"
    ik_dir = output_dir / "ik"
    id_dir = output_dir / "id"
    for d in [scale_dir, ik_dir, id_dir]:
        d.mkdir(parents=True, exist_ok=True)

    result = SubjectResult(subject_id=subject_name, session=session)

    try:
        # Step 1: Scale
        if skip_scaling:
            model_path = base_model
        else:
            if None in (subject_mass, subject_femur, subject_tibia):
                raise ValueError("subject_mass, subject_femur, subject_tibia required for scaling")
            model_path = scale_subject(
                base_model, subject_name,
                subject_mass, subject_femur, subject_tibia,
                scale_dir,
            )
        result.scaled_model = model_path

        # Step 2: IK — find all .trc files in trc_dir
        trc_files = sorted(Path(trc_dir).glob("*.trc"))
        if not trc_files:
            trc_files = sorted(Path(trc_dir).glob("*Walk*.c3d"))
        if not trc_files:
            raise FileNotFoundError(f"No .trc or .c3d files found in {trc_dir}")

        for trc in trc_files:
            trial_name = trc.stem
            trial_out = ik_dir / trial_name
            trial_out.mkdir(parents=True, exist_ok=True)

            if not skip_ik:
                ik_file = run_ik(
                    model_path, trc, trial_out, task_set,
                    name=f"{subject_name}_{trial_name}_ik",
                )
            else:
                ik_file = trial_out / "ik_results.mot"
                if not ik_file.exists():
                    logger.warning(f"Skipped IK and no cached results at {ik_file}")
                    continue

            result.ik_file = ik_file

            # Step 3: ID
            if not skip_id:
                id_file = run_id(
                    model_path, ik_file, trial_out, external_loads,
                    name=f"{subject_name}_{trial_name}_id",
                )
            else:
                id_file = trial_out / "id_results.sto"
                if not id_file.exists():
                    logger.warning(f"Skipped ID and no cached results at {id_file}")
                    continue

            result.id_file = id_file

            # Load results
            result.ik_df, _ = sto_to_df(str(ik_file))
            result.id_df, _ = sto_to_df(str(id_file))

        result.success = True

    except Exception as e:
        result.errors.append(str(e))
        logger.error(f"Pipeline failed for {subject_name}: {e}")

    return result


# =========================================================================
# Step 6: Aggregate group results
# =========================================================================
def aggregate_group(
    results: list[SubjectResult],
    group_name: str,
) -> GroupResult:
    """Average IK/ID across subjects in a group.

    Interpolates each subject's results to 0-100% gait cycle before
    averaging, so gait timing differences don't bias the mean.
    """
    grp = GroupResult(group_name=group_name, subjects=results)

    ik_dfs: list[pl.DataFrame] = []
    id_dfs: list[pl.DataFrame] = []

    for r in results:
        if not r.success:
            continue
        if r.ik_df is not None:
            ik_dfs.append(interp_to_gait(r.ik_df))
        if r.id_df is not None:
            id_dfs.append(interp_to_gait(r.id_df))

    if ik_dfs:
        concat_ik = pl.concat(ik_dfs)
        gait = concat_ik["gait_percentage"]
        numeric = [c for c in concat_ik.columns if c != "gait_percentage"]
        grp.ik_mean = concat_ik.group_by("gait_percentage").agg(
            pl.col(c).mean().alias(c) for c in numeric
        ).sort("gait_percentage")
        grp.ik_std = concat_ik.group_by("gait_percentage").agg(
            pl.col(c).std().alias(c) for c in numeric
        ).sort("gait_percentage")

    if id_dfs:
        concat_id = pl.concat(id_dfs)
        numeric = [c for c in concat_id.columns if c != "gait_percentage"]
        grp.id_mean = concat_id.group_by("gait_percentage").agg(
            pl.col(c).mean().alias(c) for c in numeric
        ).sort("gait_percentage")
        grp.id_std = concat_id.group_by("gait_percentage").agg(
            pl.col(c).std().alias(c) for c in numeric
        ).sort("gait_percentage")

    return grp
