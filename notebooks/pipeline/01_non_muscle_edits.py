# %% [markdown]
"""
# 01 Non-muscle model edits

Run this notebook first. It applies edits that do not modify muscle properties and writes a handoff model for downstream notebooks.
"""

# %% Imports
import re

import opensim as osim

from rathindlimb.processing import update_model
from rathindlimb.project import project_paths

# %%
paths = project_paths()
model_dir = paths.model_dir
xml_dir = paths.xml_dir
pipeline_dir = paths.pipeline_dir
pipeline_dir.mkdir(parents=True, exist_ok=True)

source_model_file = model_dir / "rat_hindlimb.osim"
non_muscle_out = pipeline_dir / "rat_hindlimb_non_muscle.osim"

with open(source_model_file, "r") as file:
    file_content = file.read()

terms = ["pelvis", "femur", "tibia", "foot", "sacroiliac", "hip", "knee", "ankle"]
for term in terms:
    file_content = re.sub(rf"{term}(?!_r)", f"{term}_r", file_content)

file_content = file_content.replace(".vtp", ".stl")

with open(non_muscle_out, "w") as file:
    file.write(file_content)

model = osim.Model(str(non_muscle_out))

# TODO: Remove defaults block

# %%
coords_to_lock = ["ankle_r_add", "ankle_r_int", "sacroiliac_r_flx"]
model.initSystem()
for coord_name in coords_to_lock:
    coord = model.updCoordinateSet().get(coord_name)
    coord.set_locked(True)
new_frame = [-0.00057, 0.0399598, 0.0038162]
rotation3 = [0.261799] * 14
translation1 = [
    -0.00523853,
    -0.00464648,
    -0.00404257,
    -0.00347254,
    -0.00297965,
    -0.00259079,
    -0.00229943,
    -0.00211001,
    -0.00199564,
    -0.00193207,
    -0.00187048,
    -0.00177935,
    -0.00163827,
    -0.0014134,
]
translation2 = [
    -0.0341684,
    -0.0342539,
    -0.0341856,
    -0.0339723,
    -0.0336511,
    -0.0332785,
    -0.0328898,
    -0.0325504,
    -0.0322825,
    -0.0321161,
    -0.0320632,
    -0.0321105,
    -0.0322397,
    -0.0324144,
]
translation3 = [
    0.00260302,
    0.00280341,
    0.00285365,
    0.00290375,
    0.00289358,
    0.00277318,
    0.00270235,
    0.00261105,
    0.0024695,
    0.00241714,
    0.0024041,
    0.0023809,
    0.00249641,
    0.00269104,
]
knee = osim.CustomJoint.safeDownCast(model.getJointSet().get("knee_r"))
tibia_offset = osim.PhysicalOffsetFrame.safeDownCast(knee.getChildFrame())
tibia_offset.set_translation(osim.Vec3(new_frame[0], new_frame[1], new_frame[2]))
spatial_transform = knee.get_SpatialTransform()
spatial_transform.get_rotation3().set_function(osim.Constant(rotation3[0]))
simm1 = osim.SimmSpline.safeDownCast(
    spatial_transform.get_translation1().get_function()
)
for i, value in enumerate(translation1):
    simm1.setY(i, value)
simm2 = osim.SimmSpline.safeDownCast(
    spatial_transform.get_translation2().get_function()
)
for i, value in enumerate(translation2):
    simm2.setY(i, value)
simm3 = osim.SimmSpline.safeDownCast(
    spatial_transform.get_translation3().get_function()
)
for i, value in enumerate(translation3):
    simm3.setY(i, value)
marker_set_path = xml_dir / "rat_hindlimb_unilateral_markers.xml"
marker_set = osim.MarkerSet(str(marker_set_path))
model.getMarkerSet().clearAndDestroy()
model.updateMarkerSet(marker_set)
model_1 = update_model(model, non_muscle_out)
print(f"Wrote non-muscle handoff model: {non_muscle_out}")
