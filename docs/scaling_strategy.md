# Length-Unit Scaling Strategy for Rat Hindlimb Models

## 1. Problem Statement

The rat hindlimb model features very small segment masses (e.g., foot $\approx 0.0015$ kg) and minute moments of inertia (e.g., foot $I_{xx} \approx 3 \times 10^{-8}$ kg$\cdot$m$^2$). OpenSim's Computed Muscle Control (CMC) algorithm frequently fails to converge when encountering these extremely small inertia values, as the numerical tolerances and integrator settings are typically tuned for human-scale dynamics.

To resolve this, we scale the model's length unit by a factor $k$ (e.g., converting meters to centimeters with $k=100$). This transformation increases the numerical magnitude of the inertia properties. However, scaling must be performed carefully to ensure that downstream analyses, such as inverse dynamics (ID) and CMC, produce physically meaningful results that can be related back to the original SI units.

## 2. Quantities and Their Scaling

The following table describes how physical quantities transform when the length unit is scaled by factor $k$.

| Quantity | Symbol | Units (original) | Numerical scaling | Rationale |
| --- | --- | --- | --- | --- |
| Length/position | $L$ | m | $\times k$ | Definition of unit conversion |
| Time | $t$ | s | unchanged | Independent of length unit |
| Mass (model) | $m$ | kg | depends on mode | See Section 3 |
| Gravity | $g$ | m/s$^2 \rightarrow$ new_unit/s$^2$ | $\times k$ | Acceleration in new length unit |
| Force (external) | $F$ | N | unchanged | Kept in Newtons by convention |
| COP (force plate) | $p$ | m | $\times k$ | Position in new length unit |
| Free moment (force plate) | $M$ | N$\cdot$m | $\times k$ | Force $\times$ length |
| Force vectors (force plate) | $F$ | N | unchanged | Same physical force |
| Translational coordinates | $q_{trans}$ | m | $\times k$ | Position in new length unit |
| Rotational coordinates | $q_{rot}$ | rad | unchanged | Dimensionless |
| Angular acceleration | $\alpha$ | rad/s$^2$ | unchanged | From rotational kinematics |
| Translational acceleration | $a$ | m/s$^2$ | $\times k$ | From scaled positions, same time |
| COM position | $r$ | m | $\times k$ | Position in new length unit |
| Moment of inertia | $I$ | kg$\cdot$m$^2$ | depends on mode | See Section 3 |
| Joint moment (ID output) | $\tau$ | N$\cdot$m | depends on mode | See Section 3 |

## 3. Two Scaling Modes

### 3A. Dynamically Consistent Scaling (Unit Conversion)

The goal of this mode is to ensure that inverse dynamics on the scaled model produces a torque $\tau_{new} = k \cdot \tau_{old}$, representing an exact unit conversion from N$\cdot$m to N$\cdot$(new_unit).

OpenSim's inverse dynamics computes the generalized forces for each coordinate as:

$$\tau = I \cdot \alpha + r \times (m \cdot g) + r \times F_{ext} + M_{free}$$

For $\tau_{new} = k \cdot \tau_{old}$ to hold, every term in the equation must scale by $k$:

**Inertial term:**
$$\tau_{inertial\_new} = I_{new} \cdot \alpha = k \cdot I_{old} \cdot \alpha = k \cdot \tau_{inertial\_old}$$
This requires $I_{new} = k \cdot I_{old}$.

**Gravity term:**
$$\tau_{grav\_new} = m_{new} \cdot g_{new} \cdot r_{new} = (m_{old}/k) \cdot (g \cdot k) \cdot (r \cdot k) = m \cdot g \cdot r \cdot k = k \cdot \tau_{grav\_old}$$
This requires $m_{new} = m_{old} / k$.

**External force term:**
$$\tau_{ext\_new} = r_{new} \times F = (r \cdot k) \times F = k \cdot (r \times F) = k \cdot \tau_{ext\_old}$$

**Free moment term:**
$$M_{free\_new} = M_{old} \cdot k = k \cdot M_{free\_old}$$

**Summary for Mode A:**

- Mass: $m / k$
- MOI: $I \cdot k$ (Note: `model.scale(preserveMassDist=True)` yields $I \cdot k^2$, so we must divide by $k$ afterward)
- COM: $r \cdot k$ (handled by `model.scale()`)
- Result: $\tau_{new} = k \cdot \tau_{old}$ exactly
- Residual forces: unchanged (Newtons)

The mass division is a numerical compensation rather than a physical change. OpenSim computes $F = m \cdot a$ internally. Since $a_{new} = a_{old} \cdot k$, the mass must be $m/k$ to keep the force $F$ consistent in Newtons.

**Practical issue:** In this mode, MOI only grows by $k$ while mass shrinks by $k$. If $k=100$, an original foot $I_{xx} = 3 \times 10^{-8}$ becomes $3 \times 10^{-6}$. This remains quite small and may still cause convergence issues in CMC.

### 3B. CMC-Friendly Scaling (Mass Preserved)

The goal of this mode is to maximize the increase in inertia to facilitate CMC convergence, accepting that the resulting dynamics are no longer a simple unit conversion.

In this mode, mass remains unchanged:

- Mass: $m$ (unchanged)
- MOI: $I \cdot k^2$ (as provided by `model.scale(preserveMassDist=True)`)
- COM: $r \cdot k$

This results in much larger inertias ($k^2$ growth) and preserves the physical mass values. However, the terms in the equations of motion scale non-uniformly:

| Term | Scaling |
|---|---|
| Gravity torque: $m \cdot (g \cdot k) \cdot (r \cdot k)$ | $k^2$ |
| Inertial torque: $(I \cdot k^2) \cdot \alpha$ | $k^2$ |
| External force torque: $(r \cdot k) \times F$ | $k$ |
| Free moment: $M \cdot k$ | $k$ |

Because gravity and inertial terms scale by $k^2$ while external force terms scale only by $k$:

- Joint moments from ID are not a clean multiple of the original.
- The model effectively feels $k$ times heavier relative to external forces.
- Muscle activations from CMC will over-compensate for gravity by a factor of approximately $k$.
- Muscle activations and forces are not quantitatively accurate in absolute terms.

**When to use:** Use this mode when CMC convergence is the primary requirement and results will be validated against experimental data (like EMG) rather than relying on absolute computed muscle force values.

## 4. Implementation

The scaling logic is implemented in the `rathindlimb.scale` module:

```python
from rathindlimb.scale import (
    scale_model_length,
    scale_force_plate_mot_file,
    scale_kinematics_mot_file,
    update_force_plate_setup_file,
)
```

The `scale_model_length` function currently implements Mode A (dynamically consistent).

The workflow involves:

1. `scale_model_length(model, k)`: Scales geometry, gravity, mass, MOI, and translational coordinates.
2. `scale_kinematics_mot_file(..., k)`: Scales translational coordinates in the Inverse Kinematics output.
3. `scale_force_plate_mot_file(..., k)`: Scales COP and free moments, while leaving force vectors in Newtons.
4. `update_force_plate_setup_file(...)`: Updates the XML configuration to point to the new scaled .mot file.

## 5. Choosing a Scale Factor

The following table illustrates the inertia of the right foot (the smallest body) at different $k$ values for both modes.

Original foot_r: mass = 0.001503 kg, $I_{xx} = 3.15 \times 10^{-8}$, $I_{yy} = 4.25 \times 10^{-9}$, $I_{zz} = 2.99 \times 10^{-8}$

| $k$ | Mode A mass | Mode A $I_{xx}$ | Mode B mass | Mode B $I_{xx}$ |
|---|---|---|---|---|
| 10 | $1.503 \times 10^{-4}$ | $3.15 \times 10^{-7}$ | $1.503 \times 10^{-3}$ | $3.15 \times 10^{-6}$ |
| 100 | $1.503 \times 10^{-5}$ | $3.15 \times 10^{-6}$ | $1.503 \times 10^{-3}$ | $3.15 \times 10^{-4}$ |
| 1000 | $1.503 \times 10^{-6}$ | $3.15 \times 10^{-5}$ | $1.503 \times 10^{-3}$ | $3.15 \times 10^{-2}$ |

## 6. Practical Notes

- Human-scale OpenSim models typically have segment inertias in the range of $0.01$ to $0.1$ kg$\cdot$m$^2$.
- Selecting $k=100$ with Mode B (mass preserved) brings foot inertia to approximately $3 \times 10^{-4}$, which approaches the lower bounds of human-scale magnitudes.
- Selecting $k=1000$ with Mode A provides inertia magnitudes comparable to $k=100$ with Mode B, but maintains consistent dynamics.
- Force plate force vectors are always maintained in Newtons, regardless of the scaling mode chosen.
