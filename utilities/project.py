from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    model_dir: Path
    pipeline_dir: Path
    data_dir: Path
    mesh_dir: Path
    xml_dir: Path
    attachment_dir: Path


def project_root() -> Path:
    """Return the repository root for an editable checkout."""
    return Path(__file__).resolve().parents[1]


def project_paths() -> ProjectPaths:
    """Return the standard repository paths used by the notebooks and utilities."""
    root = project_root()
    model_dir = root / "models" / "osim"
    data_dir = root / "data"
    return ProjectPaths(
        root=root,
        model_dir=model_dir,
        pipeline_dir=model_dir / ".pipeline",
        data_dir=data_dir,
        mesh_dir=root / "models" / "meshes",
        xml_dir=model_dir / "xml",
        attachment_dir=data_dir / "attachments",
    )
