"""Rat hindlimb analysis workflows.

Composes osimpy's generic OpenSim tool wrappers into rat-specific
analysis pipelines for Inverse Kinematics, Inverse Dynamics, Computed
Muscle Control, and result plotting.

Typical usage::

    from rathindlimb.analysis.pipeline import run_subject_pipeline
    from rathindlimb.analysis.plots import plot_group_comparison

    results = run_subject_pipeline(
        model="models/rat_hindlimb_bilateral.osim",
        trc_dir="data/raw/BAA01/Baseline",
        output_dir="data/results/BAA01_baseline",
    )
    plot_group_comparison(results, group_name="Control", output_dir="figures")
"""
