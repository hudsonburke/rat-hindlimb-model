"""Plotting functions for VML gait analysis.

Generates kinematic and kinetic comparison figures with SPM
significance highlights, matching the format used in the
rat-vml manuscript and thesis chapter.
"""

import logging
from pathlib import Path

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.lines import Line2D
    import seaborn as sns
except ImportError:
    plt = None
    sns = None

try:
    import spm1d
except ImportError:
    spm1d = None


# Colour palette for treatment groups
GROUP_COLORS = {
    "Control": "#4C72B0",
    "NR": "#DD8452",
    "TEMR": "#55A868",
    "HH": "#C44E52",
    "HS": "#8172B3",
    "TEMR+HH": "#937860",
    "TEMR+KG": "#DA8BC3",
}

# Mapping from treatment group codes to plot labels
GROUP_LABELS = {
    "Control": "Control",
    "NR": "No Repair",
    "TEMR": "TEMR",
    "HH": "Healy Hydrogel",
    "HS": "Healy Sponge",
    "TEMR+HH": "TEMR+H",
    "TEMR+KG": "TEMR+KG",
}

# Joint display names
JOINT_LABELS = {
    "hip_r_flx": "Hip Flexion",
    "hip_r_add": "Hip Adduction",
    "hip_r_int": "Hip Rotation",
    "knee_r_flx": "Knee Flexion",
    "ankle_r_flx": "Ankle Flexion",
    "hip_r_flx_moment": "Hip Moment",
    "hip_r_add_moment": "Hip Add Moment",
    "hip_r_int_moment": "Hip Rot Moment",
    "knee_r_flx_moment": "Knee Moment",
    "ankle_r_flx_moment": "Ankle Moment",
}


def _init_style():
    """Set up matplotlib style for manuscript-quality figures."""
    if plt is None:
        return
    sns.set_theme(
        style="ticks",
        context="paper",
        rc={
            "figure.dpi": 300,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "font.family": "sans-serif",
            "axes.linewidth": 0.8,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
        },
    )


def _spm_highlight(
    ax: "plt.Axes",
    x: np.ndarray,
    y_ref: np.ndarray,
    y_test: np.ndarray,
    alpha: float = 0.05,
    color: str = "red",
) -> None:
    """Run SPM t-test and highlight significant regions on *ax*.

    References
    ----------
    Pataky, 2010. "SPM".  https://spm1d.org/
    """
    if spm1d is None:
        return
    try:
        t = spm1d.stats.ttest_paired(y_ref, y_test)
        ti = t.inference(alpha)
        if ti.clusters:
            for cl in ti.clusters:
                start = int(x[cl.start])
                end = int(x[cl.end])
                ax.axvspan(start, end, color=color, alpha=0.15, zorder=0)
    except Exception as e:
        logger.warning(f"SPM failed: {e}")


def plot_kinematics(
    group_mean: pl.DataFrame,
    group_std: pl.DataFrame,
    control_mean: pl.DataFrame | None,
    control_std: pl.DataFrame | None,
    group_name: str,
    coord_names: list[str],
    output_path: Path,
    n_cols: int = 3,
) -> Path:
    """Generate kinematic comparison plot for one treatment group.

    Parameters
    ----------
    group_mean, group_std : pl.DataFrame
        Mean and std for the treatment group (from aggregate_group).
    control_mean, control_std : pl.DataFrame
        Mean and std for the Control group (for reference overlay).
    group_name : str
        Treatment group name (used in title and filename).
    coord_names : list[str]
        Coordinate columns to plot.
    output_path : Path
        Directory to save the figure.
    n_cols : int
        Number of subplot columns.
    """
    _init_style()
    n_rows = int(np.ceil(len(coord_names) / n_cols))

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(3.5 * n_cols, 2.5 * n_rows))
    axes_flat = axes.flatten() if n_rows > 1 else axes
    fig.suptitle(f"{GROUP_LABELS.get(group_name, group_name)} — Kinematics", fontsize=12)

    gait = group_mean["gait_percentage"].to_numpy()

    for i, coord in enumerate(coord_names):
        ax = axes_flat[i]

        # Control group reference
        if control_mean is not None and coord in control_mean.columns:
            c_mean = control_mean[coord].to_numpy()
            c_std = control_std[coord].to_numpy() if control_std is not None else None
            ax.plot(gait, c_mean, color="gray", linewidth=1.5, linestyle="--", alpha=0.6)
            if c_std is not None:
                ax.fill_between(gait, c_mean - c_std, c_mean + c_std,
                                color="gray", alpha=0.1)

        # Treatment group
        t_mean = group_mean[coord].to_numpy()
        t_std = group_std[coord].to_numpy()
        color = GROUP_COLORS.get(group_name, "#4C72B0")
        ax.plot(gait, t_mean, color=color, linewidth=2)
        ax.fill_between(gait, t_mean - t_std, t_mean + t_std,
                        color=color, alpha=0.2)

        # SPM highlights vs Control and vs NR would go here
        # _spm_highlight(ax, gait, control_mean[coord], group_mean[coord])

        ax.axvline(x=50, color="gray", linestyle=":", linewidth=0.8)
        ax.set_title(JOINT_LABELS.get(coord, coord), fontsize=9)
        ax.set_xlabel("Gait %", fontsize=8)
        ax.set_ylabel("Angle (°)", fontsize=8)
        ax.set_xlim(0, 100)
        ax.tick_params(labelsize=7)

    # Hide unused subplots
    for i in range(len(coord_names), len(axes_flat)):
        axes_flat[i].set_visible(False)

    plt.tight_layout()
    path = output_path / f"{group_name.lower().replace('+', '_')}_kinematics.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    logger.info(f"Saved {path}")
    return path


def plot_kinetics(
    group_mean: pl.DataFrame,
    group_std: pl.DataFrame,
    control_mean: pl.DataFrame | None,
    control_std: pl.DataFrame | None,
    group_name: str,
    moment_names: list[str],
    output_path: Path,
    n_cols: int = 3,
) -> Path:
    """Generate joint-moment comparison plot for one treatment group."""
    _init_style()
    n_rows = int(np.ceil(len(moment_names) / n_cols))

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(3.5 * n_cols, 2.5 * n_rows))
    axes_flat = axes.flatten() if n_rows > 1 else axes
    fig.suptitle(f"{GROUP_LABELS.get(group_name, group_name)} — Joint Moments", fontsize=12)

    gait = group_mean["gait_percentage"].to_numpy()

    for i, moment in enumerate(moment_names):
        ax = axes_flat[i]

        # Control reference
        if control_mean is not None and moment in control_mean.columns:
            c_mean = control_mean[moment].to_numpy()
            c_std = control_std[moment].to_numpy() if control_std is not None else None
            ax.plot(gait, c_mean, color="gray", linewidth=1.5, linestyle="--", alpha=0.6)
            if c_std is not None:
                ax.fill_between(gait, c_mean - c_std, c_mean + c_std,
                                color="gray", alpha=0.1)

        # Treatment group
        t_mean = group_mean[moment].to_numpy()
        t_std = group_std[moment].to_numpy()
        color = GROUP_COLORS.get(group_name, "#4C72B0")
        ax.plot(gait, t_mean, color=color, linewidth=2)
        ax.fill_between(gait, t_mean - t_std, t_mean + t_std,
                        color=color, alpha=0.2)

        ax.axvline(x=50, color="gray", linestyle=":", linewidth=0.8)
        ax.set_title(JOINT_LABELS.get(moment, moment), fontsize=9)
        ax.set_xlabel("Gait %", fontsize=8)
        ax.set_ylabel("Moment (N·m/kg)", fontsize=8)
        ax.set_xlim(0, 100)
        ax.tick_params(labelsize=7)

    for i in range(len(moment_names), len(axes_flat)):
        axes_flat[i].set_visible(False)

    plt.tight_layout()
    path = output_path / f"{group_name.lower().replace('+', '_')}_kinetics.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    logger.info(f"Saved {path}")
    return path


def generate_all_figures(
    group_results: dict[str, "GroupResult"],
    control_group: str,
    output_dir: Path,
    coord_names: list[str],
    moment_names: list[str],
) -> list[Path]:
    """Generate kinematics + kinetics figures for every treatment group.

    Returns list of saved figure paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    control = group_results.get(control_group)

    paths = []
    for name, grp in group_results.items():
        if name == control_group:
            continue
        if grp.ik_mean is None or grp.ik_std is None:
            logger.warning(f"Skipping {name}: no IK results")
            continue

        ref_mean = control.ik_mean if control else None
        ref_std = control.ik_std if control else None
        p = plot_kinematics(
            grp.ik_mean, grp.ik_std, ref_mean, ref_std,
            name, coord_names, output_dir,
        )
        paths.append(p)

        if grp.id_mean is not None and grp.id_std is not None:
            ref_mean = control.id_mean if control else None
            ref_std = control.id_std if control else None
            p = plot_kinetics(
                grp.id_mean, grp.id_std, ref_mean, ref_std,
                name, moment_names, output_dir,
            )
            paths.append(p)

    return paths
