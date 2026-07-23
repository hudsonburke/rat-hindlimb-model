"""Rat hindlimb analysis workflows.

Composes osimpy's generic OpenSim tool wrappers into rat-specific
analysis pipelines for Inverse Kinematics, Inverse Dynamics, Computed
Muscle Control, and result plotting.

Modules
-------
events     : Trial validation, gait event handling, marker gap detection
forces     : Force plate processing (Vicon→OpenSim transform, filtering, MOT export)
pipeline   : End-to-end analysis pipeline (scale, IK, ID, spline, group aggregation)
plots      : Manuscript-quality kinematic and kinetic figures
queries    : DuckDB query templates for the Rerun .rrd catalog
defaults   : Rat-specific constants (coordinate names, marker sets)
subject_groups : Subject-to-treatment-group mapping from AFIRM spreadsheet
"""
