# Third-party components

The Quantum project itself (the TouchDesigner network, the particle shader SADA FIELD,
the agent system, the CONTROL panel with MIDI learn, the HOW TO guide and the
documentation) is © 2026 Göktuğ Kahyaoğlu and licensed under the **MIT licence**
(see `LICENSE`).

## Bundled in the release download (`Quantum-macOS.zip`, folder `pylibs/`)

These packages are not in the git repository. They come only with the release
download. They are compiled for macOS on Apple Silicon with Python 3.11, which is
TouchDesigner's own Python. Each one keeps its own licence; the full licence texts
are inside each package's `*.dist-info` folder.

| package | version | licence |
|---|---|---|
| Qiskit | 2.5.2 | Apache-2.0 |
| Qiskit Aer | 0.17.2 | Apache-2.0 |
| rustworkx | 0.18.1 | Apache-2.0 |
| SciPy | 1.17.1 | BSD-3-Clause |
| stevedore | 5.9.1 | Apache-2.0 |
| dill | 0.4.1 | BSD-3-Clause |
| psutil | 7.2.2 | BSD-3-Clause |
| python-dateutil | 2.9.0.post0 | Apache-2.0 / BSD-3-Clause (dual) |
| six | 1.17.0 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |

## Inside `Quantum.toe`

| component | where | licence |
|---|---|---|
| **RGBA Delay** palette component, Derivative | `/project1/Pop_glsl_sort/rgbaDelay1` | part of TouchDesigner's Palette, used under the TouchDesigner licence |
| TouchDesigner default operators and components (lights, camera, button) | throughout | TouchDesigner licence |

TouchDesigner itself is © Derivative and is not included. Get it from https://derivative.ca.
