.PHONY: all sync clean 01 02 03 tsl lengths

# Default: run the full pipeline
all: sync 01 02 03

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
sync:
	uv sync

# ---------------------------------------------------------------------------
# Pipeline steps (run in order)
# ---------------------------------------------------------------------------

# 01 — Non-muscle edits: naming conventions, knee joint, coordinate locks
01: sync
	cd notebooks/pipeline && uv run python 01_non_muscle_edits.py

# 02 — Muscle edits: Millard conversion, mesh registration, via-point paths,
#     Johnson 2011 parameters, optimized TSL values
02: sync
	cd notebooks/pipeline && uv run python 02_muscle_edits.py

# 03 — Bilateral mirroring: bodies, joints, muscles, marker set
03: sync
	cd notebooks/pipeline && uv run python 03_mirroring.py

# ---------------------------------------------------------------------------
# Analysis notebooks
# ---------------------------------------------------------------------------

# Recompute tendon slack lengths using tsl-optimization package
tsl: sync
	uv run jupyter nbconvert --to notebook --execute notebooks/tsl_optimization.ipynb

# Analyze muscle length profiles across range of motion
lengths: sync
	cd notebooks && uv run quarto render muscle_lengths.qmd

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------
clean:
	rm -rf models/osim/.pipeline
