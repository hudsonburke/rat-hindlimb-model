"""Rat hindlimb musculoskeletal model utilities."""

from __future__ import annotations

from pathlib import Path

# Base directory for bundled model files
_MODELS_DIR = Path(__file__).parent / "models"


def models_dir() -> Path:
    """Return the path to the bundled models directory."""
    return _MODELS_DIR


def bilateral_model() -> Path:
    """Return the path to the bilateral muscle model."""
    return _MODELS_DIR / "output" / "rat_hindlimb_bilateral.osim"


def unilateral_model() -> Path:
    """Return the path to the unilateral muscle model."""
    return _MODELS_DIR / "output" / "rat_hindlimb_unilateral.osim"


def bilateral_scale_setup() -> Path:
    """Return the path to the bilateral scale setup XML."""
    return _MODELS_DIR / "input" / "xml" / "rat_hindlimb_bilateral_scale_setup.xml"


def bilateral_markers() -> Path:
    """Return the path to the bilateral marker set XML."""
    return _MODELS_DIR / "input" / "xml" / "rat_hindlimb_bilateral_markers.xml"


def unilateral_markers() -> Path:
    """Return the path to the unilateral marker set XML."""
    return _MODELS_DIR / "input" / "xml" / "rat_hindlimb_unilateral_markers.xml"
