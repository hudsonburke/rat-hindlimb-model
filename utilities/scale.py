from typing import TypedDict, Callable, cast
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import polars as pl

# Third-party imports that may not be available to static type checkers in CI
# environments (opensim/osimpy/ezc3d). Use inline ignores so the language server
# won't emit missing-import errors for these optional runtime deps.
import opensim as osim  # type: ignore[reportMissingImports]
from osimpy.io.read import sto_to_df  # type: ignore[reportMissingImports]
from osimpy.io.write import export_mot  # type: ignore[reportMissingImports]

from .project import project_root
# Drawn from Johnson's opensim rat model (in millimeters to match recorded values in .c3d files)

BASE_FEMUR_LENGTH = float(np.linalg.norm([-0.0035, -0.0312, -0.005]) * 1000)
BASE_TIBIA_LENGTH = float(np.linalg.norm([0.0016, 0.039, -0.0037]) * 1000)


class RatScalingParameters(TypedDict):
    Mass: float
    RFemurLength: float
    RTibiaLength: float
    LFemurLength: float
    LTibiaLength: float
    RFootLength: float
    LFootLength: float


def _manual_scale_factors(
    parameters: RatScalingParameters,
) -> dict[str, tuple[float, float, float]]:
    right_femur_scale = parameters["RFemurLength"] / BASE_FEMUR_LENGTH
    right_tibia_scale = parameters["RTibiaLength"] / BASE_TIBIA_LENGTH
    left_femur_scale = parameters["LFemurLength"] / BASE_FEMUR_LENGTH
    left_tibia_scale = parameters["LTibiaLength"] / BASE_TIBIA_LENGTH

    return {
        "femur_r": (right_femur_scale, right_femur_scale, right_femur_scale),
        "tibia_r": (right_tibia_scale, right_tibia_scale, right_tibia_scale),
        "femur_l": (left_femur_scale, left_femur_scale, left_femur_scale),
        "tibia_l": (left_tibia_scale, left_tibia_scale, left_tibia_scale),
    }


PROJECT_ROOT = project_root()
model_path = PROJECT_ROOT / "models" / "osim"
unscaled_model_path = model_path / "rat_hindlimb_bilateral.osim"
xml_path = model_path / "xml"
marker_set_path = xml_path / "rat_hindlimb_bilateral_markers.xml"
generic_setup_path = xml_path / "rat_hindlimb_bilateral_scale_setup.xml"


# ---------------------------------------------------------------------------
# Hicks regression equations for segment inertial properties
# All inputs: mass in kg, lengths in mm
# All outputs: mass in kg, COM in m, MOI in kg*m^2
# ---------------------------------------------------------------------------

_SEGMENT_MASS_COEFFICIENTS: dict[str, tuple[float, float]] = {
    "thigh": (8.3313, 3.6883),
    "shank": (3.2096, 3.0047),
    "foot": (2.2061, 0.87788),
}

_SEGMENT_COM_COEFFICIENTS: dict[
    str,
    tuple[
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
    ],
] = {
    #   (x_coeff, x_divisor), (y_coeff, y_divisor), (z_coeff, z_divisor)
    #   x = length * x_coeff / x_divisor
    #   y = mass * y_coeff * (y_divisor / 100)    [negative percentage]
    #   z = mass * z_coeff * (z_divisor / 100) * z_sign
    "thigh": (
        (-8.7844332, 100000),
        (0.148741316, -42.118041),
        (0.098448042, 2.00427791),
    ),
    "shank": (
        (0.09004923, -2.43352222),
        (67.363643, 100000),
        (0.07731125, 1.71207065),
    ),
    "foot": (
        (0.04627387, -4.294993),
        (-42.78009, 100000),
        (0.07246637, 0.6265934),
    ),
}

_SEGMENT_MOI_COEFFICIENTS: dict[str, tuple[float, float, float]] = {
    "thigh": (0.00189568, 0.00143871, 0.00248006),
    "shank": (0.00104229, 0.00029337, 0.00104734),
    "foot": (0.000384786, 0.0000518802, 0.000364591),
}


def segment_mass(segment: str, mass: float) -> float:
    a, b = _SEGMENT_MASS_COEFFICIENTS[segment]
    return (a * mass + b) / 1000


def segment_com(
    segment: str, side: str, length: float, mass: float
) -> tuple[float, float, float]:
    z_sign = -1 if side[0].upper() == "L" else 1
    coeffs = _SEGMENT_COM_COEFFICIENTS[segment]

    if segment == "thigh":
        x = length * coeffs[0][0] / coeffs[0][1]
        y = mass * coeffs[1][0] * (coeffs[1][1] / 100)
        z = mass * coeffs[2][0] * (coeffs[2][1] / 100) * z_sign
    elif segment == "shank":
        x = mass * coeffs[0][0] * (coeffs[0][1] / 100)
        y = length * coeffs[1][0] / coeffs[1][1]
        z = (mass * coeffs[2][0]) * (coeffs[2][1] / 100) * z_sign
    else:
        x = (mass * coeffs[0][0]) * (coeffs[0][1] / 100)
        y = length * coeffs[1][0] / coeffs[1][1]
        z = (mass * coeffs[2][0]) * (coeffs[2][1] / 100) * z_sign

    return (x, y, z)


def segment_moi(segment: str, length: float, mass: float) -> tuple[float, float, float]:
    cx, cy, cz = _SEGMENT_MOI_COEFFICIENTS[segment]
    length_m_sq = (length / 1000) ** 2
    return (
        cx * mass * length_m_sq,
        cy * mass * length_m_sq,
        cz * mass * length_m_sq,
    )


def thigh_mass(mass: float) -> float:
    return segment_mass("thigh", mass)


def thigh_com(
    side: str, femur_length: float, mass: float
) -> tuple[float, float, float]:
    return segment_com("thigh", side, femur_length, mass)


def thigh_moi(femur_length: float, mass: float) -> tuple[float, float, float]:
    return segment_moi("thigh", femur_length, mass)


def shank_mass(mass: float) -> float:
    return segment_mass("shank", mass)


def shank_com(
    side: str, tibia_length: float, mass: float
) -> tuple[float, float, float]:
    return segment_com("shank", side, tibia_length, mass)


def shank_moi(tibia_length: float, mass: float) -> tuple[float, float, float]:
    return segment_moi("shank", tibia_length, mass)


def foot_mass(mass: float) -> float:
    return segment_mass("foot", mass)


def foot_com(side: str, foot_length: float, mass: float) -> tuple[float, float, float]:
    return segment_com(
        "foot", side, foot_length, mass
    )  # TODO: Still need to check the weird thing Brody does with this in the old code


def foot_moi(foot_length: float, mass: float) -> tuple[float, float, float]:
    return segment_moi("foot", foot_length, mass)


def scaling_parameters_from_c3d(file_path: str) -> RatScalingParameters:
    # ezc3d is a runtime-only dependency; annotate the import so static
    # analysis does not error when the package isn't available in the LSP env.
    import ezc3d  # type: ignore[reportMissingImports]

    c3d = ezc3d.c3d(file_path)
    if "PROCESSING" not in c3d.parameters:
        raise ValueError("C3D file does not contain PROCESSING parameters.")
    params = {}
    for key in RatScalingParameters.__annotations__.keys():
        if key not in c3d.parameters["PROCESSING"]:
            raise ValueError(f"Marker {key} not found in C3D file.")
        params[key] = c3d.parameters["PROCESSING"][key]["value"][0]
    return RatScalingParameters(**params)


def _set_body_properties(
    body: osim.Body,
    mass: float,
    mass_center: tuple[float, float, float],
    moments: tuple[float, float, float],
) -> None:
    body.set_mass(mass)
    body.set_mass_center(osim.Vec3(*mass_center))
    body.set_inertia(osim.Vec6(*moments, 0, 0, 0))


def _apply_segment_properties(
    model_path: Path,
    parameters: RatScalingParameters,
) -> None:
    model = osim.Model(str(model_path))
    model.setName(model_path.stem)
    model_body_set: osim.BodySet = model.getBodySet()
    subject_mass = parameters["Mass"]
    for side in ["L", "R"]:
        side_short = side.lower()

        femur_length = parameters[f"{side}FemurLength"]
        thigh: osim.Body = model_body_set.get(f"femur_{side_short}")
        _set_body_properties(
            thigh,
            thigh_mass(subject_mass),
            thigh_com(side, femur_length, subject_mass),
            thigh_moi(femur_length, subject_mass),
        )

        tibia_length = parameters[f"{side}TibiaLength"]
        shank: osim.Body = model_body_set.get(f"tibia_{side_short}")
        _set_body_properties(
            shank,
            shank_mass(subject_mass),
            shank_com(side, tibia_length, subject_mass),
            shank_moi(tibia_length, subject_mass),
        )

        foot_length = parameters[f"{side}FootLength"]
        foot: osim.Body = model_body_set.get(f"foot_{side_short}")
        _set_body_properties(
            foot,
            foot_mass(subject_mass),
            foot_com(side, foot_length, subject_mass),
            foot_moi(foot_length, subject_mass),
        )

    model.finalizeConnections()
    model.printToXML(str(model_path))


def scale_opensim_model(
    name: str,
    trc_file_name: str,
    parameters: RatScalingParameters,
    output_dir: str = ".",
    initial_time: float = 0.0,
    final_time: float | None = None,
    scaled_model_name: str | None = None,
    scale_factors_name: str | None = None,
    setup_name: str | None = None,
):
    """
    Create scaled OpenSim model from a static rat trial.
    """

    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    if scaled_model_name is None:
        scaled_model_name = f"{name}_scaled.osim"
    if scale_factors_name is None:
        scale_factors_name = f"{name}_scale.xml"
    if setup_name is None:
        setup_name = f"{name}_scale_setup.xml"

    # Import scale tool lazily (runtime only). The type checker may not be able
    # to resolve ``osimpy.tools`` in the analysis environment, so add a
    # selective ignore for that import.
    from osimpy.tools import ScaleSettings  # type: ignore[reportMissingImports]

    scale_settings = ScaleSettings(
        name=name,
        setup_path=generic_setup_path,
        model_path=unscaled_model_path,
        results_directory=output_path,
        marker_set_path=marker_set_path,
        marker_path=Path(trc_file_name).resolve(),
        output_model_file=scaled_model_name,
        output_scale_file=scale_factors_name,
        scale_factors=_manual_scale_factors(parameters),
        preserve_mass_distribution=False,
        subject_mass=parameters["Mass"],
        initial_time=initial_time,
        final_time=final_time,
        use_marker_placer=True,
    )
    result = scale_settings.run()
    if result.success and result.scaled_model_file is not None:
        _apply_segment_properties(result.scaled_model_file, parameters)
    else:
        raise RuntimeError(f"Scaling failed with errors: {result.errors}")
    return


def scale_model_length(model: osim.Model, scale_factor: float) -> osim.Model:
    """
    Rescale the length unit of a model for dynamically consistent unit conversion.

    After scaling, inverse dynamics on the scaled model with correspondingly
    scaled kinematics and force-plate data produces joint moments that equal
    the original moments multiplied by *scale_factor* (the unit-conversion
    ratio for torque, N·m → N·new_unit).

    ``model.scale()`` with *preserveMassDist=True* scales COM by *k* and
    MOI by *k²* while leaving mass unchanged.  For the equations of motion
    to remain consistent (every generalised-force term scaling by the same
    factor *k*), mass must be divided by *k* and MOI must equal its original
    value times *k* (not *k²*).  See ``_scale_body_masses_for_unit_conversion``
    for the derivation.
    """

    scaled_model = model.clone()
    state = scaled_model.initSystem()

    scaled_model.scale(state, _uniform_scale_set(scaled_model, scale_factor), True)
    _scale_body_masses_for_unit_conversion(scaled_model, scale_factor)
    _scale_gravity(scaled_model, scale_factor)
    _scale_translational_coordinates(scaled_model, scale_factor)
    scaled_model.finalizeConnections()

    return scaled_model


def _uniform_scale_set(model: osim.Model, scale_factor: float) -> osim.ScaleSet:
    scale_set = osim.ScaleSet()
    scale_factors = osim.Vec3(scale_factor, scale_factor, scale_factor)
    body_set: osim.BodySet = model.getBodySet()

    for body_index in range(body_set.getSize()):
        body: osim.Body = body_set.get(body_index)
        scale = osim.Scale()
        scale.setApply(True)
        scale.setSegmentName(body.getName())
        scale.setScaleFactors(scale_factors)
        scale_set.cloneAndAppend(scale)

    return scale_set


def _scale_gravity(model: osim.Model, scale_factor: float) -> None:
    gravity = model.get_gravity()
    model.set_gravity(
        osim.Vec3(
            gravity.get(0) * scale_factor,
            gravity.get(1) * scale_factor,
            gravity.get(2) * scale_factor,
        )
    )


def _scale_body_masses_for_unit_conversion(
    model: osim.Model, scale_factor: float
) -> None:
    """Adjust mass and MOI so that every term in the equations of motion
    scales by the same factor *k* (= *scale_factor*).

    ``model.scale(preserveMassDist=True)`` already set:
        COM  → COM_orig × k      (correct)
        mass → mass_orig          (needs ÷ k)
        MOI  → MOI_orig × k²     (needs ÷ k to reach MOI_orig × k)

    After this function:
        mass_new = mass_orig / k
        MOI_new  = MOI_orig × k   (= MOI_after_scale / k)

    Derivation (rotational DOF, all other DOFs analogous):
        τ_new = I_new·α  +  r_new × (m_new·g_new)  +  r_new × F  +  M_free_new
              = (I·k)·α  +  (r·k)×(m/k · g·k)      +  (r·k)×F   +  M·k
              =  k·(I·α  +  r×(m·g)                 +  r×F        +  M)
              =  k · τ_old                                                    ✓
    """
    body_set: osim.BodySet = model.getBodySet()
    for i in range(body_set.getSize()):
        body: osim.Body = body_set.get(i)

        body.set_mass(body.get_mass() / scale_factor)

        inertia = body.get_inertia()
        body.set_inertia(
            osim.Vec6(
                inertia.get(0) / scale_factor,
                inertia.get(1) / scale_factor,
                inertia.get(2) / scale_factor,
                inertia.get(3) / scale_factor,
                inertia.get(4) / scale_factor,
                inertia.get(5) / scale_factor,
            )
        )


def _scale_translational_coordinates(model: osim.Model, scale_factor: float) -> None:
    coordinate_set: osim.CoordinateSet = model.getCoordinateSet()

    for coordinate_index in range(coordinate_set.getSize()):
        coordinate: osim.Coordinate = coordinate_set.get(coordinate_index)
        if coordinate.getMotionType() != osim.Coordinate.Translational:
            continue

        coordinate.setDefaultValue(coordinate.getDefaultValue() * scale_factor)
        coordinate.setRangeMin(coordinate.getRangeMin() * scale_factor)
        coordinate.setRangeMax(coordinate.getRangeMax() * scale_factor)


def scale_force_plate_mot(
    data: pl.DataFrame,
    scale_factor: float,
    point_identifiers: tuple[str, ...] = ("_px", "_py", "_pz", "cop"),
    torque_identifiers: tuple[str, ...] = ("moment", "torque"),
) -> pl.DataFrame:
    """Scale point-of-application and torque columns in force plate data.

    Force vector columns (e.g. force1_vx) are intentionally left unscaled
    because force magnitudes do not change under length-unit conversion.
    """
    point_columns = _matching_columns(data.columns, point_identifiers)
    torque_columns = _matching_columns(data.columns, torque_identifiers)
    return _scale_dataframe_columns(data, point_columns | torque_columns, scale_factor)


def scale_force_plate_mot_file(
    input_path: str | Path,
    output_path: str | Path,
    scale_factor: float,
    point_identifiers: tuple[str, ...] = ("_px", "_py", "_pz", "cop"),
    torque_identifiers: tuple[str, ...] = ("moment", "torque"),
) -> Path:
    return _transform_mot_file(
        input_path,
        output_path,
        lambda data: scale_force_plate_mot(
            data,
            scale_factor,
            point_identifiers=point_identifiers,
            torque_identifiers=torque_identifiers,
        ),
    )


def scale_kinematics_mot(
    data: pl.DataFrame,
    model: osim.Model | str | Path,
    scale_factor: float,
) -> pl.DataFrame:
    translational_coordinates = _translational_coordinate_names(model)
    columns_to_scale = {
        column
        for column in data.columns
        if _is_translational_kinematics_column(column, translational_coordinates)
    }
    return _scale_dataframe_columns(data, columns_to_scale, scale_factor)


def scale_kinematics_mot_file(
    input_path: str | Path,
    output_path: str | Path,
    model: osim.Model | str | Path,
    scale_factor: float,
) -> Path:
    return _transform_mot_file(
        input_path,
        output_path,
        lambda data: scale_kinematics_mot(data, model, scale_factor),
    )


def update_force_plate_setup_file(
    input_path: str | Path,
    output_path: str | Path,
    datafile: str | Path,
    data_source_name: str | None = None,
) -> Path:
    input_path = Path(input_path)
    output_path = Path(output_path)
    datafile_path = Path(datafile)
    source_name = data_source_name or datafile_path.name

    tree = ET.parse(input_path)
    root = tree.getroot()

    datafile_elements = root.findall(".//datafile")
    for element in datafile_elements:
        element.text = str(datafile)

    data_source_elements = root.findall(".//data_source_name")
    for element in data_source_elements:
        element.text = source_name

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return output_path


def _transform_mot_file(
    input_path: str | Path,
    output_path: str | Path,
    transform: Callable[[pl.DataFrame], pl.DataFrame],
) -> Path:
    # Accept either str or Path for convenience and convert immediately.
    input_path = Path(input_path)
    output_path = Path(output_path)

    data, metadata = sto_to_df(input_path)
    scaled_data = transform(data)
    # output_path is already a Path
    export_mot(str(output_path), scaled_data, metadata)
    return output_path


def _scale_dataframe_columns(
    data: pl.DataFrame, columns_to_scale: set[str], scale_factor: float
) -> pl.DataFrame:
    if not columns_to_scale:
        return data

    return data.with_columns(
        [
            pl.col(column).cast(pl.Float64, strict=False) * scale_factor
            for column in data.columns
            if column in columns_to_scale
        ]
    )


def _matching_columns(columns: list[str], identifiers: tuple[str, ...]) -> set[str]:
    lowered = tuple(i.lower() for i in identifiers)
    return {c for c in columns if any(i in c.lower() for i in lowered)}


def _translational_coordinate_names(model) -> set[str]:
    """Return the set of translational coordinate names for `model`.

    The input may be an OpenSim Model instance or a filesystem path to an
    .osim file. We conservatively accept any type to avoid static analysis
    problems in environments where the OpenSim Python bindings are not
    visible to the language server.
    """
    if not isinstance(model, osim.Model):
        model = osim.Model(str(Path(model)))

    coordinate_set: osim.CoordinateSet = model.getCoordinateSet()
    return {
        coordinate_set.get(i).getName()
        for i in range(coordinate_set.getSize())
        if coordinate_set.get(i).getMotionType() == osim.Coordinate.Translational
    }


def _is_translational_kinematics_column(
    column_name: str, translational_coordinates: set[str]
) -> bool:
    if column_name == "time":
        return False

    if column_name in translational_coordinates:
        return True

    path_tokens = [token for token in column_name.split("/") if token]
    if len(path_tokens) >= 2 and path_tokens[-1] in {"value", "speed", "accel"}:
        return path_tokens[-2] in translational_coordinates

    if column_name.endswith(("_u", "_udot")):
        base_name = column_name.rsplit("_", 1)[0]
        return base_name in translational_coordinates

    return False


# ---------------------------------------------------------------------------
# Dynamic-magnitude scaling (for numerical conditioning)
# ---------------------------------------------------------------------------


def scale_model_dynamics_inplace(model, scale_factor: float, scale_muscles: bool = True) -> None:
    """Multiply every inertial quantity in *model* by *scale_factor*.

    This scales body masses and inertias (×scale_factor) and, optionally,
    muscle max isometric forces (×scale_factor). This produces a dynamically
    similar model when external forces and actuator strengths are scaled by the
    same factor.

    The function mutates the provided ``model`` object in-place; call
    ``model.printToXML(path)`` to persist the result.
    """
    body_set = model.getBodySet()
    for i in range(body_set.getSize()):
        body: osim.Body = body_set.get(i)
        # scale mass
        body.set_mass(body.get_mass() * scale_factor)

        # scale inertia (Vec6)
        inertia = body.get_inertia()
        body.set_inertia(
            osim.Vec6(
                inertia.get(0) * scale_factor,
                inertia.get(1) * scale_factor,
                inertia.get(2) * scale_factor,
                inertia.get(3) * scale_factor,
                inertia.get(4) * scale_factor,
                inertia.get(5) * scale_factor,
            )
        )

    if scale_muscles:
        try:
            muscles = model.getMuscles()
            for i in range(muscles.getSize()):
                m = muscles.get(i)
                # use the public API to read/modify max isometric force
                try:
                    current = m.get_max_isometric_force()
                    m.set_max_isometric_force(current * scale_factor)
                except Exception:
                    # Some muscle types may not expose the same API; ignore
                    continue
        except Exception:
            # No muscles or unexpected model structure — skip
            pass


def scale_model_dynamics_file(
    input_model_path: str | Path,
    output_model_path: str | Path,
    scale_factor: float,
    scale_muscles: bool = True,
) -> Path:
    """Scale inertial/muscle quantities inside a .osim XML file.

    This function edits the modeller XML directly. It multiplies:
      - <Body>/<mass> by scale_factor
      - every number inside <inertia> by scale_factor
      - every <max_isometric_force> by scale_factor (optional)
      - every <optimal_force> by scale_factor (optional)

    The parser is conservative and only touches tags it recognises; formatting
    of the written file will be the default ElementTree representation.
    """
    input_path = Path(input_model_path)
    output_path = Path(output_model_path)
    tree = ET.parse(str(input_path))
    root = tree.getroot()

    # Bodies: mass + inertia
    for body in root.findall('.//Body'):
        mass_el = body.find('mass')
        if mass_el is not None and mass_el.text and mass_el.text.strip():
            try:
                mass_val = float(mass_el.text.strip())
                mass_el.text = repr(mass_val * scale_factor)
            except Exception:
                pass

        inertia_el = body.find('inertia')
        if inertia_el is not None and inertia_el.text and inertia_el.text.strip():
            parts = inertia_el.text.strip().split()
            try:
                new_parts = [repr(float(p) * scale_factor) for p in parts]
                inertia_el.text = ' '.join(new_parts)
            except Exception:
                pass

    # Muscles: max_isometric_force
    if scale_muscles:
        for mif in root.findall('.//max_isometric_force'):
            if mif is None or mif.text is None:
                continue
            try:
                v = float(mif.text.strip())
                mif.text = repr(v * scale_factor)
            except Exception:
                continue

    # Actuators/reserves: optimal_force
    for opt in root.findall('.//optimal_force'):
        if opt is None or opt.text is None:
            continue
        try:
            v = float(opt.text.strip())
            opt.text = repr(v * scale_factor)
        except Exception:
            continue

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(output_path), encoding='utf-8', xml_declaration=True)
    return output_path


def scale_force_plate_mot_dynamic(
    data: pl.DataFrame,
    scale_factor: float,
    *,
    force_identifiers: tuple[str, ...] = ("force", "fx", "fy", "fz", "_vx", "_vy", "_vz"),
    torque_identifiers: tuple[str, ...] = ("moment", "torque"),
) -> pl.DataFrame:
    """Scale force and torque columns in a force-plate MOT (dynamic scaling).

    Unlike ``scale_force_plate_mot`` (which implements unit-conversion
    semantics and leaves force magnitudes unchanged), this function multiplies
    force and torque columns by *scale_factor* so the recorded external loads
    match a model whose inertias have been multiplied by the same factor.
    """
    # Identify force-like and torque-like columns using substring matching
    force_columns = _matching_columns(data.columns, force_identifiers)
    torque_columns = _matching_columns(data.columns, torque_identifiers)
    cols = force_columns | torque_columns
    return _scale_dataframe_columns(data, cols, scale_factor)


def scale_force_plate_mot_file_dynamic(
    input_path: str | Path,
    output_path: str | Path,
    scale_factor: float,
    *,
    force_identifiers: tuple[str, ...] = ("force", "fx", "fy", "fz", "_vx", "_vy", "_vz"),
    torque_identifiers: tuple[str, ...] = ("moment", "torque"),
) -> Path:
    return _transform_mot_file(
        input_path,
        output_path,
        lambda data: scale_force_plate_mot_dynamic(
            data, scale_factor, force_identifiers=force_identifiers, torque_identifiers=torque_identifiers
        ),
    )
