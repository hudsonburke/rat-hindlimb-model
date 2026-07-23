# RatHindlimb

## Description

This repository contains code and data to generate a bilateral musculoskeletal model of the rat hindlimb in OpenSim, based on the original model from Johnson et al. (2008) updated to utilize attachment points from the work of Young et al. (2017), a more robust knee joint, muscle parameters from Johnson et al. (2011), and estimated tendon slack lengths based on the methods of Manal & Buchanan (2004) all mirrored to the contralateral limb. The model is intended for use in simulations of rat hindlimb biomechanics, including inverse kinematics, inverse dynamics, and computed muscle control. Quarto handles execution caching for model-generation notebooks/documents.

## Quickstart

### Prerequisites

- [git](https://git-scm.com/install/)
- [uv](https://docs.astral.sh/uv/)
- [Quarto](https://quarto.org/), if you want to render `index.qmd`

`uv` manages the Python environment, locks the dependency graph, installs OpenSim from PyPI, and pulls `osimpy` plus `tsl-optimization` from the Git sources declared in `pyproject.toml`.

### Installation

```shell
# Clone the repository
git clone <this-repo-url>
cd rat-hindlimb-model

# Create the locked environment and install the package editable
uv sync
```

### Workflow structure

- `utilities/`: reusable library code imported as `rathindlimb`
- `notebooks/pipeline/*.py`: canonical editable marimo workflow for model edits
- `notebooks/tsl_optimization.py`: canonical editable marimo workflow for tendon slack estimation
- `notebooks/pipeline/*.qmd`: narrative/publish copies of the pipeline
- `notebooks/pipeline/*.ipynb` and `notebooks/tsl_optimization.ipynb`: notebook exchange/render copies
- `index.qmd`: narrative-only overview; it does not execute the pipeline during render

### Usage

Run the canonical model-edit pipeline in order:

1. `uv run marimo edit notebooks/pipeline/01_non_muscle_edits.py`
2. `uv run marimo edit notebooks/pipeline/02_muscle_edits.py`
3. `uv run marimo edit notebooks/pipeline/03_mirroring.py`

Estimate tendon slack length in marimo:

- `uv run marimo edit notebooks/tsl_optimization.py`

The generated `data/parameters/tsl_comparison.csv` keeps both `Full ROM TSL (mm)` and `Walk TSL (mm)`, but the model-edit pipeline uses `Walk TSL (mm)` for updates. The full-ROM column is retained as a diagnostic comparison because Cartesian combinations of joint limits can create physiologically unreachable poses and infeasible no-buckling solves.

Render the narrative document:

```shell
quarto render index.qmd
```

Final published models are written to:

- `models/osim/rat_hindlimb_unilateral.osim`
- `models/osim/rat_hindlimb_unilateral_no_muscles.osim`
- `models/osim/rat_hindlimb_bilateral.osim`
- `models/osim/rat_hindlimb_bilateral_no_muscles.osim`

## Example Results

See HuggingFace repository hudsonburke/rat-hindlimb-mocap

## Contributing

### Repo Structure

This repo works best when reusable logic stays in `rathindlimb` and notebooks remain thin orchestration layers:

- reusable code in `utilities/`
- canonical pipeline notebooks in `notebooks/pipeline/*.py`
- Quarto documents for narrative/reporting only
- `.ipynb` copies as exchange artifacts, not the primary editing surface

### TODO

- [ ] Add a generated exchange/export path for the tendon slack notebook copies
- [ ] Separate muscle analysis and validation into testable library functions
- [ ] Add model validation tests

## References and Acknowledgements

- Johnson 2008
- Johnson 2011
- Eng 2008
- Manal & Buchanan 2004
- Young 2017
- Open3D
- Hicks
- Dienes
- Delp? / OpenSim
- Charles 2016

## Citing

This model is associated with the publication ...

If you use this repository in your research, please cite:

```json


```
