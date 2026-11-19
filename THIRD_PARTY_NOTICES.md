# Third-party components

The Quantum project itself (the TouchDesigner network, the particle shader SADA FIELD,
the agent system, the CONTROL panel with MIDI learn, the HOW TO guide and the
documentation) is © 2026 Göktuğ Kahyaoğlu and licensed under the **MIT licence**
(see `LICENSE`).

## Optional: Qiskit

Since version 1.1 nothing is bundled besides `Quantum.toe`. The quantum draw runs as a
state-vector simulation in NumPy, which ships with TouchDesigner. If Qiskit and Qiskit
Aer (both Apache-2.0) are installed where TouchDesigner's Python can find them, the
piece uses them instead. They are not part of this project or its download.

## Inside `Quantum.toe`

| component | where | licence |
|---|---|---|
| **RGBA Delay** palette component, Derivative | `/project1/Pop_glsl_sort/rgbaDelay1` | part of TouchDesigner's Palette, used under the TouchDesigner licence |
| TouchDesigner default operators and components (lights, camera, button) | throughout | TouchDesigner licence |

TouchDesigner itself is © Derivative and is not included. Get it from https://derivative.ca.
