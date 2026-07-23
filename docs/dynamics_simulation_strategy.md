# Dynamics Simulation Strategy for Rodent Musculoskeletal Models

## 1. Problem Statement

Simulating the musculoskeletal dynamics of small animals like rats presents unique numerical challenges compared to human-scale models. The primary issue stems from the extremely small inertial properties of the limb segments:

* **Foot mass:** $\approx 0.00150$ kg
* **Foot $I_{xx}$:** $\approx 3.15 \times 10^{-8}$ kg$\cdot$m$^2$

During locomotion, these segments experience significant external loads. For instance, a peak Ground Reaction Force (GRF) of $2.33$ N applied to the foot generates angular accelerations of approximately $317,460$ rad/s$^2$:

$$\alpha \approx \frac{\tau}{I} \approx \frac{F \cdot r}{I}$$

OpenSim's traditional forward-dynamics-based tools, such as Residual Reduction Analysis (RRA) and Computed Muscle Control (CMC), are generally unable to handle these orders of magnitude. The stiff dynamics cause the numerical integrator to fail as it attempts to reduce the step size infinitesimally to maintain stability.

Furthermore, there is a lack of published literature demonstrating successful RRA/CMC applications on rodent models. Notably, Charles et al. (2018), in their study of mouse dynamics, explicitly utilized Static Optimization followed by Forward Dynamics, intentionally avoiding the RRA/CMC pipeline.

## 2. Approaches Attempted

Four distinct computational strategies were evaluated to resolve the dynamics of the rat hindlimb.

### Approach 1: Length-Unit Scaling + RRA

The model was scaled by a factor of $k=10$ (converting meters to decimeters) to numerically increase the inertia values (see `docs/scaling_strategy.md`). While RRA was able to complete the simulation time range, it failed to maintain joint integrity. Specifically, the ankle joints became unconstrained, reaching unrealistic ranges of $[-113^\circ, 146^\circ]$.

* **Conclusion:** Scaling improves numerical conditioning but does not address fundamental joint instabilities at this scale.

### Approach 2: Coordinate Limit Forces (CLF)

To prevent the joint excursions observed in Approach 1, six `CoordinateLimitForce` components were added to the ankle coordinates. Various stiffness values (0.1, 1, 3, 5, 10 Nm/deg) were tested:

* **Stiffness 0.1:** Insufficient to constrain the joint (reached $381^\circ, -1137^\circ$).
* **Stiffness 10:** Caused immediate integrator failure upon reaching the limit.
* **Stiffness 1, 3, 5:** All failed consistently at $t \approx 2.898$ s.
* **Conclusion:** CLF cannot resolve the underlying numerical stiffness in rodent-scale forward integration.

### Approach 3: Static Optimization (SO)

Static Optimization succeeded both with and without muscle physiology constraints across 117 frames ($t=2.87$ to $3.45$ s).

* **Pros:** Produces instantaneous muscle force estimates without requiring forward integration.
* **Cons:** Neglects muscle excitation-contraction dynamics and does not provide a forward-simulated trajectory.

### Approach 4: MocoTrack (Direct Collocation)

* **v1:** Failed. Missing `TabOpUseAbsoluteStateNames()` caused zero state tracking.
* **v2:** **Succeeded.** Successfully solved the tracking problem using direct collocation. Validated across all 5 BAA01 walking trials with 100% success rate.
* **v3:** Failed to improve on v2. Finer mesh (10 ms) + stricter reserves degraded solution quality (16× worse tracking, 2.6× slower).

## 3. Why RRA/CMC Fails on Rodent Models

The failure of RRA/CMC on rodent-scale models is due to three primary factors:

1. **Stiff Dynamics:** Forward integration (Runge-Kutta) is ill-suited for systems where tiny inertias are subjected to large external forces. The resulting catastrophic accelerations force the integrator into a failure state.
2. **Informational Limits:** In OpenSim, the `clamped=true` setting for coordinates is informational only. It does NOT enforce limits during forward dynamics. This has been [confirmed by OpenSim developers](https://github.com/opensim-org/opensim-core/issues/1256); only `CoordinateLimitForce` provides physical constraints during integration.
3. **Numerical Instability:** As shown in Section 2, even when `CoordinateLimitForce` is applied, the high stiffness required to stop the high-acceleration segments typically crashes the integrator.

## 4. MocoTrack — The Solution

Direct collocation (via MocoTrack) succeeds where forward integration fails because it transforms the simulation into a mathematical optimization problem.

* **Mechanism:** It solves the entire trajectory simultaneously as a single Nonlinear Programming (NLP) problem using CasADi and IPOPT.
* **Advantage:** There is no "step-by-step" integration. Constraints (including joint limits and system dynamics) are satisfied across all mesh points concurrently, avoiding the infinitesimally small step sizes that plague RRA/CMC.

### Critical Configuration for Rat Models

To achieve convergence with the rat hindlimb model, the following configuration details are required:

| Parameter/Operator | Requirement | Rationale |
| :--- | :--- | :--- |
| `TabOpUseAbsoluteStateNames()` | **Required** | Ensures IK names (e.g., `sacrum_pitch`) match Moco state paths. Without this, references are silently ignored. |
| `TabOpConvertDegreesToRadians()` | **Required** | IK files (`.mot`) are typically in degrees; Moco requires radians. |
| `ModOpAddReserves(optimal_force)` | 0.01 - 0.1 | Low optimal force ensures the solver prioritizes muscle forces over reserve actuators. |
| Coordinate Unlocking | Manual | Locked coordinates in the `.osim` must be unlocked, then constrained via tight `MocoBounds` ($\pm 1 \times 10^{-6}$ of default) in the problem. |
| `ModOpReplaceMusclesWithDeGrooteFregly2016()` | **Required** | Standard muscles must be replaced for compatibility with Moco's smooth optimization requirements. |
| Muscle Simplifications | Optional | `ModOpIgnoreTendonCompliance()` and `ModOpIgnorePassiveFiberForcesDGF()` aid initial convergence. |
| `ModOpScaleActiveFiberForceCurveWidthDGF(1.5)`| Recommended | Widening the active force-length curve improves robustness against IK noise. |

## 5. MocoTrack v2 Results

The v2 simulation provided the first successful full-body dynamics solution for this model. It was subsequently validated on all 5 BAA01 Baseline walking trials.

### Single-Trial Results (Walk05)

| Metric | Value |
| :--- | :--- |
| **Status** | Solve_Succeeded |
| **Iterations** | 611 |
| **Solver Duration** | 4787 s (80 min) |
| **Objective Value** | 0.009539 |
| State Tracking Term | 0.006931 |
| Control Effort Term | 0.002608 |
| **Mesh Interval** | 20 ms ($\sim 29$ mesh points) |
| **Convergence Tolerance** | $1 \times 10^{-3}$ |
| **Constraint Tolerance** | $1 \times 10^{-4}$ |
| **Rotational Tracking RMS** | $0.20^\circ$ (Excellent) |
| **Translational Tracking RMS** | sacrum_y = 28 mm (Needs improvement) |
| **Reserves** | Max $|val| = 0.55$ (sacrum_pitch), Mean $|val| = 0.075$ |

**Muscle Activations:**

* Range: $[0.01, 1.00]$
* Mean: $0.094 \pm 0.103$ (std)
* Correlation with SO: Mean = 0.25 (12/76 muscles with corr > 0.5)

### Cross-Trial Validation (All 5 BAA01 Trials)

All 5 BAA01 Baseline walking trials were solved using the identical v2 configuration. Results demonstrate consistent convergence and solution quality.

| Trial | Status | Iterations | Time (min) | Objective | State Tracking | Max Reserve | Mean Activation |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| Walk05 | Succeeded | 611 | 80 | 0.00954 | 0.00693 | 0.55 | 0.094 |
| Walk06 | Succeeded | 613 | 100 | 0.00792 | 0.00538 | 0.63 | 0.115 |
| Walk08 | Succeeded | 994 | 128 | 0.00722 | 0.00478 | 0.58 | 0.106 |
| Walk11 | Succeeded | 908 | 83 | 0.00770 | 0.00486 | 0.56 | 0.153 |
| Walk14 | Succeeded | 949 | 83 | 0.00511 | 0.00295 | 0.60 | 0.135 |

**Cross-trial summary:**

* **Success rate:** 5/5 (100%)
* **Objective:** mean = 0.0075, CV = 19.0%
* **Rotational tracking RMS:** mean = 0.24°, max = 0.84° (all trials excellent)
* **Translational tracking:** sacrum_y RMS = 16–28 mm across trials
* **Reserves:** max $|val|$ = 0.56–0.63 across all trials (well below 1.0)
* **Muscle activations:** mean = 0.094–0.153, all muscles show meaningful variation (no stuck muscles)
* **Cross-trial muscle consistency:** median CV = 24.2% (physiologically reasonable inter-trial variability)

## 6. MocoTrack v3 Refinements

Building on the v2 success, v3 attempted to reduce reliance on reserves and improve translational tracking through stricter constraints and a finer mesh.

### v3 Results

| Metric | Value |
| :--- | :--- |
| **Status** | Solve_Succeeded |
| **Iterations** | 761 |
| **Solver Duration** | 12543 s (209 min) |
| **Objective Value** | 0.290519 |
| State Tracking Term | 0.112584 |
| Control Effort Term | 0.177935 |
| **Mesh Interval** | 10 ms ($\sim 58$ mesh points) |
| **Reserves** | Max $|val| = 2.27$ (sacroiliac_l), Mean $|val| = 0.21$ |

**Muscle Activations:**

* Range: $[0.01, 1.00]$
* Mean: $0.156$

### Conclusion: v2 vs. v3 Comparison

The v3 configuration (finer mesh + stricter reserves) produced **worse** results across all key quality metrics.

| Metric | v2 (20 ms mesh) | v3 (10 ms mesh) | Change |
| :--- | :--- | :--- | :--- |
| Solver Duration | 80 min | 209 min | 2.6x slower |
| State Tracking | 0.006931 | 0.112584 | 16x worse |
| Max Reserve | 0.55 | 2.27 | 4x higher |
| Mean Activation | 0.094 | 0.156 | 66% higher |

The solver could not satisfy the tighter constraints (lower `optimal_force`, higher penalty) while maintaining tracking quality on the finer mesh. Instead, it accepted significantly higher tracking errors to meet the dynamical constraints. For this model scale, the v2 configuration represents the optimal "sweet spot" for accuracy and performance.

## 7. Practical Recommendations

1. **Final Configuration (v2):** The 20 ms mesh (~29 points) is the recommended configuration. Finer meshes (10 ms) increase solve time by 2.6x but degrade solution quality for this specific model.
2. **Abandon RRA/CMC:** For rodent musculoskeletal models, forward integration is likely to fail regardless of scaling. Direct collocation (MocoTrack) is the recommended path.
3. **Use Static Optimization for Screening:** SO is a fast and reliable way to check if your model and external forces are consistent before attempting Moco.
4. **Validate Moco State Paths:** Always use `TabOpUseAbsoluteStateNames()`. Verify that the tracking error is non-zero in the log to ensure references are being tracked.
5. **Solver Performance & Parallelization:**
    * `MocoCasADiSolver.set_parallel(1)` enables multi-core evaluation across mesh points (enabled by default).
    * There are diminishing returns for parallelization above ~6 cores (Denton et al. 2023).
    * GPU acceleration is not supported by the CasADi/IPOPT backend.
    * For batch processing: run multiple trials in parallel on separate cores rather than attempting to speed up a single trial.
6. **Iterative Refinement:** Start with a coarse mesh (20-30 points) and high reserve strengths ($0.1$ optimal force) to achieve initial convergence. Use successful solutions to warm-start finer, more constrained problems if necessary, though v2 results suggest further refinement may be counter-productive.

## 8. osimpy Integration Layer

All three dynamics tools (MocoTrack, RRA, SO) now have Pydantic-based wrappers in the `osimpy` library, with rat-specific preset factories in `rathindlimb`.

### Architecture

```
osimpy/tools/         # General-purpose Pydantic wrappers
├── tool.py           # ToolSettings[ResultT] base, ToolResult base
├── rra.py            # RRASettings(ToolSettings[RRAResult])
├── so.py             # SOSettings(ToolSettings[SOResult])
├── cmc.py            # CMCSettings(ToolSettings[CMCResult])
├── id.py             # IDSettings(ToolSettings[IDResult])
├── ik.py             # IKSettings(ToolSettings[IKResult])
└── scale.py          # ScaleSettings(ToolSettings[ScaleResult])

osimpy/moco/          # Moco wrappers (different tool.run() pattern)
├── track.py          # MocoTrackSettings, MocoTrackResult
└── inverse.py        # MocoInverseSettings, MocoInverseResult

rathindlimb/utilities/  # Rat-specific presets
├── moco.py           # prepare_moco_model(), rat_mocotrack_settings()
└── dynamics.py       # rat_rra_settings(), rat_so_settings()
```

The `ToolSettings → create_tool() → run() → ToolResult` pattern gives every tool:

* Pydantic validation of all inputs before OpenSim is invoked
* Automatic setup XML serialization for reproducibility
* Structured result objects with lazy data loading

### Usage Examples

**MocoTrack** (direct collocation):

```python
from rathindlimb import prepare_moco_model, rat_mocotrack_settings

moco_model = prepare_moco_model("scaled_scaled.osim")
settings = rat_mocotrack_settings(
    model_path=moco_model,
    coordinates_path="Walk05_ik.mot",
    external_loads_path="Walk05_fp_setup.xml",
    results_directory="MocoTrack_v2",
    initial_time=2.87, final_time=3.45,
    reserve_optimal_force=0.1,
    reserve_penalty=10.0,
)
result = settings.run()
df, meta = result.load_solution()
```

**RRA** (residual reduction):

```python
from rathindlimb import rat_rra_settings

settings = rat_rra_settings(
    model_path="scaled_scaled.osim",
    desired_kinematics_path="Walk05_ik.mot",
    external_loads_path="Walk05_fp_setup.xml",
    results_directory="RRA_results",
    force_set_paths=["rat_hindlimb_bilateral_rra_actuators.xml"],
    task_set_path="rat_hindlimb_bilateral_tasks.xml",
    initial_time=2.87, final_time=3.45,
)
result = settings.run()
kinematics_df, _ = result.load_kinematics()
forces_df, _ = result.load_actuation_forces()
```

**Static Optimization**:

```python
from rathindlimb import rat_so_settings

settings = rat_so_settings(
    model_path="scaled_scaled.osim",
    coordinates_path="Walk05_ik.mot",
    external_loads_path="Walk05_fp_setup.xml",
    results_directory="SO_results",
    use_muscle_physiology=True,
    initial_time=2.87, final_time=3.45,
)
result = settings.run()
activations_df, _ = result.load_activations()
forces_df, _ = result.load_forces()
```

### Rat-Specific Defaults

| Tool | Parameter | Rat Default | Rationale |
| :--- | :--- | :--- | :--- |
| RRA | `adjusted_com_body` | `"spine"` | Equivalent to `"torso"` in human models |
| RRA | `replace_force_set` | `True` | Replace model forces with reserve actuators |
| RRA | `lowpass_cutoff_frequency` | 15 Hz | Standard for rat gait |
| SO | `use_model_force_set` | `True` | Include model muscles in optimization |
| SO | `replace_force_set` | `False` | Append additional actuators, don't replace |
| MocoTrack | Locked coords | Tight `MocoBounds` | 6 coordinates unlocked + constrained |
| MocoTrack | Reserve penalty | 10–100× | Force solver to prefer muscles over reserves |

## 9. File Reference

| Category | File Path |
| :--- | :--- |
| **Model** | `scaled_moco.osim` (Unlocked coordinates) |
| **IK Data** | `BAA01_Baseline_Walk05_ik.mot` |
| **GRF Data** | `BAA01_Baseline_Walk05_FP.mot`, `_fp_setup.xml` |
| **Moco Scripts** | `run_mocotrack_v2.py`, `run_mocotrack_v3.py`, `run_mocotrack_v2_batch.py` |
| **Analysis** | `analyze_mocotrack_v2.py`, `analyze_mocotrack_v3.py` |
| **Solutions** | `MocoTrack_v2/moco_solution_v2.sto` (Walk05), `MocoTrack_v2_Walk{06,08,11,14}/` |
| **Batch Analysis** | `analyze_mocotrack_v2_batch.py`, `mocotrack_v2_batch_summary.txt` |
| **osimpy RRA** | `osimpy/tools/rra.py` |
| **osimpy SO** | `osimpy/tools/so.py` |
| **osimpy MocoTrack** | `osimpy/moco/track.py` |
| **Rat presets** | `rathindlimb/utilities/moco.py`, `dynamics.py` |
| **Integration tests** | `test_mocotrack_integration.py`, `test_rra_so_integration.py`, `test_id_ik_scale_integration.py` |
