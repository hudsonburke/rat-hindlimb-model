"""RRA and Static Optimization presets for the rat hindlimb model.

Handles rat-specific concerns that don't belong in the general-purpose
osimpy library:
  - Default integrator settings tuned for rat-scale inertias
  - COM adjustment body for the rat spine
  - Force set and task file paths from the standard model layout
"""

from __future__ import annotations

from pathlib import Path


def rat_rra_settings(
    model_path: str | Path,
    desired_kinematics_path: str | Path,
    results_directory: str | Path,
    force_set_paths: list[str | Path],
    task_set_path: str | Path,
    external_loads_path: str | Path | None = None,
    *,
    initial_time: float | None = None,
    final_time: float | None = None,
    adjusted_com_body: str = "spine",
    output_model_file: str = "adjusted_model.osim",
    lowpass_cutoff_frequency: float = 15.0,
    maximum_integrator_step_size: float = 0.001,
    minimum_integrator_step_size: float = 1e-8,
    integrator_error_tolerance: float = 1e-5,
    maximum_number_of_integrator_steps: int = 20000,
) -> "RRASettings":
    """Build an RRASettings pre-configured for the rat hindlimb model.

    Parameters
    ----------
    model_path
        Path to the .osim model file.
    desired_kinematics_path
        IK .mot output with desired coordinate trajectories.
    results_directory
        Where to write results.
    force_set_paths
        Reserve actuator XML files (e.g. ``rat_hindlimb_bilateral_rra_actuators.xml``).
    task_set_path
        RRA tracking tasks XML (e.g. ``rat_hindlimb_bilateral_tasks.xml``).
    external_loads_path
        External loads XML (force plate data).
    adjusted_com_body
        Body whose COM is adjusted to reduce residuals.  Default ``"spine"``
        for the rat model (analogous to ``"torso"`` in human models).
    lowpass_cutoff_frequency
        Low-pass filter for IK data.  Default 15 Hz per rat gait conventions.
    """
    from osimpy.tools.rra import RRASettings

    kwargs: dict = dict(
        name="rat_hindlimb_rra",
        model_path=Path(model_path),
        desired_kinematics_path=Path(desired_kinematics_path),
        results_directory=Path(results_directory),
        force_set_paths=[Path(p) for p in force_set_paths],
        task_set_path=Path(task_set_path),
        replace_force_set=True,
        adjust_com_to_reduce_residuals=True,
        adjusted_com_body=adjusted_com_body,
        output_model_file=output_model_file,
        lowpass_cutoff_frequency=lowpass_cutoff_frequency,
        maximum_integrator_step_size=maximum_integrator_step_size,
        minimum_integrator_step_size=minimum_integrator_step_size,
        integrator_error_tolerance=integrator_error_tolerance,
        maximum_number_of_integrator_steps=maximum_number_of_integrator_steps,
    )
    if external_loads_path is not None:
        kwargs["external_loads_path"] = Path(external_loads_path)
    if initial_time is not None:
        kwargs["initial_time"] = initial_time
    if final_time is not None:
        kwargs["final_time"] = final_time

    return RRASettings(**kwargs)


def rat_so_settings(
    model_path: str | Path,
    coordinates_path: str | Path,
    results_directory: str | Path,
    external_loads_path: str | Path | None = None,
    force_set_paths: list[str | Path] | None = None,
    *,
    initial_time: float | None = None,
    final_time: float | None = None,
    use_muscle_physiology: bool = True,
    lowpass_cutoff_frequency: float = 15.0,
    activation_exponent: float = 2.0,
    optimizer_convergence_criterion: float = 1e-4,
    optimizer_max_iterations: int = 100,
) -> "SOSettings":
    """Build an SOSettings pre-configured for the rat hindlimb model.

    Parameters
    ----------
    model_path
        Path to the .osim model file.
    coordinates_path
        IK .mot output with coordinate trajectories.
    results_directory
        Where to write results.
    external_loads_path
        External loads XML (force plate data).
    force_set_paths
        Additional actuator XML files.  Default empty (model forces only).
    use_muscle_physiology
        Enforce force-length-velocity constraints.  Set ``False`` for
        a simpler optimisation when muscle physiology causes convergence
        issues at rat scale.
    lowpass_cutoff_frequency
        Low-pass filter for IK data.  Default 15 Hz per rat gait conventions.
    """
    from osimpy.tools.so import SOSettings

    kwargs: dict = dict(
        name="rat_hindlimb_so",
        model_path=Path(model_path),
        coordinates_path=Path(coordinates_path),
        results_directory=Path(results_directory),
        force_set_paths=[Path(p) for p in (force_set_paths or [])],
        replace_force_set=False,
        use_model_force_set=True,
        use_muscle_physiology=use_muscle_physiology,
        lowpass_cutoff_frequency_for_coordinates=lowpass_cutoff_frequency,
        activation_exponent=activation_exponent,
        optimizer_convergence_criterion=optimizer_convergence_criterion,
        optimizer_max_iterations=optimizer_max_iterations,
    )
    if external_loads_path is not None:
        kwargs["external_loads_path"] = Path(external_loads_path)
    if initial_time is not None:
        kwargs["initial_time"] = initial_time
    if final_time is not None:
        kwargs["final_time"] = final_time

    return SOSettings(**kwargs)
