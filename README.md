# RatHindlimb

## Description

This repository contains code and data to generate a bilateral musculoskeletal model of the rat hindlimb in OpenSim, based on the original model from Johnson et al. (2008) updated to utilize attachment points from the work of Young et al. (2017), a more robust knee joint, muscle parameters from Johnson et al. (2011), and estimated tendon slack lengths based on the methods of Manal & Buchanan (2004) all mirrored to the contralateral limb. The model is intended for use in simulations of rat hindlimb biomechanics, including inverse kinematics, inverse dynamics, and computed muscle control. Quarto handles execution caching for model-generation notebooks/documents.

## Quickstart

- Clone the repository with submodules
- Install with [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

```shell
# Clone the repository
git clone --recurse-submodules https://github.com/hudsonburke/rat-hindlimb-model.git
cd rat-hindlimb-model

# Install dependencies with uv
uv sync

# Or with pip
pip install -e .
```

### Usage

Render with Quarto (narrative only):

``` shell
quarto render index.qmd
```

Run the model pipeline end-to-end:

``` shell
make      # Runs steps 01 → 02 → 03 in order
```

Or run individual steps:

``` shell
make 01   # Non-muscle edits (naming, knee joint, coordinate locks)
make 02   # Muscle edits (Millard conversion, via-point paths, parameters)
make 03   # Bilateral mirroring
```

Recompute tendon slack lengths from motion data:

``` shell
make tsl  # Executes notebooks/tsl_optimization.ipynb
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

### TODO

- [x] Switch from package structure to more script-based structure for model edit
- [ ] Separate out muscle specific edits
- [x] Move computational things in index.qmd to isolated scripts
- [x] Package install instructions and change src.* to rathindlimb.*
  - Package uses utilities/ directory via package-dir mapping
- [x] Add osimpy and tsl-optimization as uv source dependencies
- [ ] Formalize muscle analysis functions
- [ ] Create tests for model validation
- [x] Clean up intermediate model edits
- [x] Migrate from conda to uv for dependency management
- [ ] Organize script usage into Makefile
- [x] Add Makefile for pipeline orchestration
- [x] Consolidate pipeline to single format (scripts, not triplicate notebooks+qmd+py)

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
