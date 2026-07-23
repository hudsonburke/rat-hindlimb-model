"""Moco utilities for the rat hindlimb model.

Handles rat-specific concerns that don't belong in the general-purpose
osimpy library:
  - Unlocking coordinates that are locked in the original model
    (Moco requires all coordinates to be unlocked)
  - Preset configurations tuned for rat-scale inertias
"""

from __future__ import annotations

import logging
from pathlib import Path

import opensim as osim

logger = logging.getLogger(__name__)

LOCKED_COORDINATE_DEFAULTS: dict[str, float] = {
    "sacroiliac_r_flx": 0.06457718,
    "ankle_r_add": -0.08726646,
    "ankle_r_int": 0.0,
    "sacroiliac_l_flx": 0.06457718,
    "ankle_l_add": -0.08726646,
    "ankle_l_int": 0.0,
}

TRANSLATION_STATE_PATHS: list[str] = [
    "/jointset/ground_spine/sacrum_x/value",
    "/jointset/ground_spine/sacrum_y/value",
    "/jointset/ground_spine/sacrum_z/value",
]


def prepare_moco_model(
    model_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """Unlock all locked coordinates so the model is compatible with Moco.

    Moco's direct-collocation formulation requires all coordinates to be
    unlocked.  The original rat hindlimb model has 6 locked coordinates
    (sacroiliac flexion, ankle add/int on both sides).  This function
    sets them all to ``locked=false`` and writes a new .osim file.

    Parameters
    ----------
    model_path
        Path to the original .osim model.
    output_path
        Where to write the unlocked model.  Defaults to
        ``<model_stem>_moco.osim`` next to the original.

    Returns
    -------
    Path
        Absolute path to the written model file.
    """
    model_path = Path(model_path)
    if output_path is None:
        output_path = model_path.with_name(f"{model_path.stem}_moco.osim")
    output_path = Path(output_path)

    model = osim.Model(str(model_path))
    coord_set = model.getCoordinateSet()

    unlocked = []
    for i in range(coord_set.getSize()):
        coord = coord_set.get(i)
        if coord.get_locked():
            coord.set_locked(False)
            unlocked.append(coord.getName())

    if unlocked:
        logger.info("Unlocked %d coordinates: %s", len(unlocked), unlocked)
    else:
        logger.info("No locked coordinates found — model already Moco-compatible")

    model.printToXML(str(output_path))
    return output_path.resolve()


def rat_mocotrack_settings(
    model_path: str | Path,
    coordinates_path: str | Path,
    results_directory: str | Path,
    external_loads_path: str | Path | None = None,
    *,
    initial_time: float | None = None,
    final_time: float | None = None,
    initial_guess_file: str | Path | None = None,
    reserve_optimal_force: float = 0.1,
    reserve_penalty: float = 10.0,
    mesh_interval: float = 0.02,
    max_iterations: int = 1000,
    translation_tracking_weight: float = 1.0,
    solution_filename: str = "moco_solution.sto",
) -> "MocoTrackSettings":
    """Build a MocoTrackSettings pre-configured for the rat hindlimb model.

    This wires up the coordinate constraints for formerly-locked joints,
    boosts translation tracking weights, and penalises reserve actuators —
    all the rat-specific tuning discovered during v2/v3 development.
    """
    from osimpy.moco.track import (
        CoordinateConstraint,
        ControlWeightPattern,
        MocoTrackSettings,
        StateWeight,
    )

    coordinate_constraints = [
        CoordinateConstraint(name=name, value=val)
        for name, val in LOCKED_COORDINATE_DEFAULTS.items()
    ]

    state_weights = [
        StateWeight(state_path=p, weight=translation_tracking_weight)
        for p in TRANSLATION_STATE_PATHS
    ] if translation_tracking_weight != 1.0 else []

    control_weight_patterns = [
        ControlWeightPattern(pattern=".*reserve.*", weight=reserve_penalty)
    ] if reserve_penalty != 1.0 else []

    kwargs: dict = dict(
        name="rat_hindlimb_tracking",
        model_path=Path(model_path),
        coordinates_path=Path(coordinates_path),
        results_directory=Path(results_directory),
        solution_filename=solution_filename,
        reserve_optimal_force=reserve_optimal_force,
        mesh_interval=mesh_interval,
        max_iterations=max_iterations,
        coordinate_constraints=coordinate_constraints,
        state_weights=state_weights,
        control_weight_patterns=control_weight_patterns,
    )
    if external_loads_path is not None:
        kwargs["external_loads_path"] = Path(external_loads_path)
    if initial_time is not None:
        kwargs["initial_time"] = initial_time
    if final_time is not None:
        kwargs["final_time"] = final_time
    if initial_guess_file is not None:
        kwargs["initial_guess_file"] = Path(initial_guess_file)

    return MocoTrackSettings(**kwargs)
