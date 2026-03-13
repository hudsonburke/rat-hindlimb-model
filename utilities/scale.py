from typing import TypedDict
import opensim as osim
import numpy as np
from pathlib import Path
import ezc3d
from osimpy.tools import ScaleSettings

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


project_root = Path(__file__).resolve().parents[1]
model_path = project_root / "models" / "osim"
unscaled_model_path = model_path / "rat_hindlimb_bilateral.osim"
xml_path = model_path / "xml"
marker_set_path = xml_path / "rat_hindlimb_bilateral_markers.xml"
generic_setup_path = xml_path / "rat_hindlimb_bilateral_scale_setup.xml"


# ---------------------------------------------------------------------------
# Hicks regression equations for segment inertial properties
# All inputs: mass in kg, lengths in mm
# All outputs: mass in kg, COM in m, MOI in kg*m^2
# ---------------------------------------------------------------------------


def thigh_mass(mass: float):
    return (8.3313 * mass + 3.6883) / 1000


def thigh_com(
    side: str, femur_length: float, mass: float
) -> tuple[float, float, float]:
    z_sign = -1 if side[0].upper() == "L" else 1
    return (
        femur_length * (-8.7844332 / 100000),
        mass * 0.148741316 * (-42.118041 / 100),
        mass * 0.098448042 * (2.00427791 / 100) * z_sign,
    )


def thigh_moi(femur_length: float, mass: float) -> tuple[float, float, float]:
    return (
        (0.00189568) * (mass) * (femur_length / 1000) ** 2,
        (0.00143871) * (mass) * (femur_length / 1000) ** 2,
        (0.00248006) * (mass) * (femur_length / 1000) ** 2,
    )


def shank_mass(mass: float):
    return (3.2096 * mass + 3.0047) / 1000


def shank_com(
    side: str, tibia_length: float, mass: float
) -> tuple[float, float, float]:
    z_sign = -1 if side[0].upper() == "L" else 1
    return (
        (mass) * 0.09004923 * (-2.43352222 / 100),
        tibia_length * (67.363643 / 100000),
        (mass * 0.07731125) * (1.71207065 / 100) * z_sign,
    )


def shank_moi(tibia_length: float, mass: float) -> tuple[float, float, float]:
    return (
        (0.00104229) * (mass) * (tibia_length / 1000) ** 2,
        (0.00029337) * (mass) * (tibia_length / 1000) ** 2,
        (0.00104734) * (mass) * (tibia_length / 1000) ** 2,
    )


def foot_mass(mass: float):
    return (2.2061 * mass + 0.87788) / 1000


def foot_com(side: str, foot_length: float, mass: float) -> tuple[float, float, float]:
    z_sign = -1 if side[0].upper() == "L" else 1
    return (
        (mass * 0.04627387) * (-4.294993 / 100),
        foot_length * (-42.78009 / 100000),
        (mass * 0.07246637) * (0.6265934 / 100) * z_sign,
    )  # TODO: Still need to check the weird thing Brody does with this in the old code


def foot_moi(foot_length: float, mass: float) -> tuple[float, float, float]:
    return (
        (0.000384786) * (mass) * (foot_length / 1000) ** 2,
        (0.0000518802) * (mass) * (foot_length / 1000) ** 2,
        (0.000364591) * (mass) * (foot_length / 1000) ** 2,
    )


def scaling_parameters_from_c3d(file_path: str) -> RatScalingParameters:
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
    subject_mass: float,
) -> None:
    model = osim.Model(str(model_path))
    model.setName(model_path.stem)
    model_body_set: osim.BodySet = model.getBodySet()

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

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if scaled_model_name is None:
        scaled_model_name = f"{name}_scaled.osim"
    if scale_factors_name is None:
        scale_factors_name = f"{name}_scale.xml"
    if setup_name is None:
        setup_name = f"{name}_scale_setup.xml"

    scaled_model_path = output_path / scaled_model_name
    scale_factors_path = output_path / scale_factors_name

    scale_settings = ScaleSettings(
        name=name,
        setup_file=generic_setup_path,
        model_file=unscaled_model_path,
        results_directory=output_path,
        marker_set_path=str(marker_set_path),
        marker_file=str(Path(trc_file_name).resolve()),
        output_model_file=str(scaled_model_path),
        output_scale_file=str(scale_factors_path),
        scale_factors=_manual_scale_factors(parameters),
        preserve_mass_distribution=False,
        subject_mass=parameters["Mass"],
        initial_time=initial_time,
        final_time=final_time,
        use_marker_placer=True,
    )
    result = scale_settings.run()
    if result.success:
        _apply_segment_properties(scaled_model_path, parameters, parameters["Mass"])
    else:
        raise RuntimeError(f"Scaling failed with errors: {result.errors}")
    return
