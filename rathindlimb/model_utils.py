from pathlib import Path

import opensim as osim


def update_model(
    model: osim.Model,
    save_path: str | Path,
) -> osim.Model:
    """
    Update and save an OpenSim model to XML.

    Returns the reloaded model.
    """
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    model.finalizeFromProperties()
    model.finalizeConnections()
    model.printToXML(str(save_path))
    return osim.Model(str(save_path))


def remove_muscles(model: osim.Model) -> osim.Model:
    """Remove all muscles from a model in-place and return the same model."""
    force_set: osim.ForceSet = model.upd_ForceSet()
    indices_to_remove = []
    for i in range(force_set.getSize()):
        if osim.Muscle.safeDownCast(force_set.get(i)) is not None:
            indices_to_remove.append(i)
    for i in indices_to_remove[::-1]:
        force_set.remove(i)
    return model


def thelen_to_millard(
    thelen: osim.Thelen2003Muscle,
) -> osim.Millard2012EquilibriumMuscle:
    """Convert a single Thelen2003Muscle to Millard2012EquilibriumMuscle."""
    try:
        thelen = osim.Thelen2003Muscle.safeDownCast(thelen)
    except Exception as e:
        raise TypeError(
            f"Input muscle {thelen.getName()} is not a Thelen2003Muscle object: {e}"
        )

    millard = osim.Millard2012EquilibriumMuscle()
    millard.setName(thelen.getName())
    millard.set_path(thelen.getGeometryPath())
    millard.set_max_isometric_force(thelen.get_max_isometric_force())
    millard.set_optimal_fiber_length(thelen.get_optimal_fiber_length())
    millard.set_tendon_slack_length(thelen.get_tendon_slack_length())
    millard.set_pennation_angle_at_optimal(thelen.get_pennation_angle_at_optimal())
    millard.set_ignore_tendon_compliance(thelen.get_ignore_tendon_compliance())
    millard.set_fiber_damping(0.1)
    millard.set_default_activation(thelen.get_default_activation())
    millard.set_minimum_activation(thelen.get_minimum_activation())
    millard.set_ActiveForceLengthCurve(osim.ActiveForceLengthCurve())
    millard.set_ForceVelocityCurve(osim.ForceVelocityCurve())
    millard.set_FiberForceLengthCurve(osim.FiberForceLengthCurve())
    millard.set_TendonForceLengthCurve(osim.TendonForceLengthCurve())
    return millard


def model_thelen_to_millard(model: osim.Model) -> osim.Model:
    """Convert all Thelen2003Muscle instances to Millard2012EquilibriumMuscle."""
    force_set: osim.ForceSet = model.upd_ForceSet()
    indices_to_remove = []
    for i in range(force_set.getSize()):
        try:
            muscle = osim.Thelen2003Muscle.safeDownCast(force_set.get(i))
            if muscle is None:
                continue
        except Exception:
            continue
        millard = thelen_to_millard(muscle)
        force_set.append(millard)
        indices_to_remove.append(i)
    for i in indices_to_remove[::-1]:
        force_set.remove(i)
    return model
