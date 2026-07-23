import marimo

__generated_with = "0.23.9"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Tendon slack length estimation

    Canonical tendon slack workflow. Computes the comparison table and writes `data/parameters/tsl_comparison.csv`.

    The table keeps both **Full ROM** and **Walk** estimates, but downstream model updates should use **Walk TSL (mm)**. The full-ROM column is diagnostic only: Cartesian combinations of independent joint limits can create physiologically unreachable poses that violate the updated optimizer's no-buckling constraint.
    """)
    return


@app.cell
def _():
    from rathindlimb.project import project_paths
    from rathindlimb.tsl import TslWorkflowConfig, estimate_tsl_comparison, write_tsl_comparison

    paths = project_paths()
    model_file = paths.model_dir / "rat_hindlimb_unilateral.osim"
    control_file = paths.data_dir / "motion" / "Control.mat"
    johnson_parameters_file = paths.data_dir / "parameters" / "johnson_2011_parameters.csv"
    output_file = paths.data_dir / "parameters" / "tsl_comparison.csv"
    config = TslWorkflowConfig()
    return (
        TslWorkflowConfig,
        config,
        control_file,
        estimate_tsl_comparison,
        johnson_parameters_file,
        model_file,
        output_file,
        write_tsl_comparison,
    )


@app.cell
def _(config, control_file, estimate_tsl_comparison, johnson_parameters_file, model_file):
    tsl_df, tsl_results, failures = estimate_tsl_comparison(
        model_file,
        control_file,
        johnson_parameters_file,
        config=config,
        strict=False,
    )
    return failures, tsl_df, tsl_results


@app.cell
def _(output_file, tsl_df, write_tsl_comparison):
    written_file = write_tsl_comparison(output_file, tsl_df)
    return (written_file,)


@app.cell(hide_code=True)
def _(failures, mo, tsl_df, written_file):
    failure_lines = [f"- `{muscle}`: {message}" for muscle, message in sorted(failures.items())]
    failure_md = "\n".join(failure_lines) if failure_lines else "None."
    mo.vstack(
        [
            mo.md(f"Wrote `{written_file}`."),
            mo.md(f"## Optimization failures\n{failure_md}"),
            mo.ui.table(tsl_df.to_pandas()),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
