# Environment notes

This project deliberately uses **two Python worlds**, and they must be able to
see each other in one interpreter. This page explains why, so future-you does
not "fix" the setup into a broken state.

## The two worlds

|                    | system Python (`/usr/bin/python3`)                | project venv (`.venv/`)                |
|--------------------|----------------------------------------------------|----------------------------------------|
| Installed by       | apt (`/usr/lib/python3/dist-packages`, `/opt/ros/…`) | pip (`scripts/setup.sh`)              |
| Provides           | `rclpy`, ROS 2 message packages                    | `mediapipe`, newer `opencv`, `numpy`   |
| Used by            | `ros2` CLI, launch files, controllers              | the vision nodes (which also need `rclpy`) |

## Why the venv uses `--system-site-packages`

1. `rclpy` is compiled C++ bound to the system Python 3.12 and is **not
   pip-installable**. It lives in `/opt/ros/jazzy/lib/python3.12/site-packages`
   and becomes importable when you `source /opt/ros/jazzy/setup.bash` (it is
   added to `PYTHONPATH`).
2. Ubuntu 24.04 blocks `pip install` into the system Python by design (PEP 668,
   "externally managed environment"). Forcing it with `--break-system-packages`
   risks breaking apt-managed ROS packages.
3. So the venv is created from the **same** system interpreter (`python3.12`,
   same ABI) with `--system-site-packages`. MediaPipe from pip shadows apt's
   numpy/opencv *inside the venv only*, while `rclpy` is visible via
   `PYTHONPATH`. Both import in the same process — that is the whole trick.

Rebuild from scratch at any time:

```bash
rm -rf .venv models
scripts/setup.sh
```

## Sourcing order

`scripts/run.sh` handles this; manually it is:

```bash
source /opt/ros/jazzy/setup.bash
source .venv/bin/activate
```

Rules of thumb:

- **Never** `pip install rclpy` — it comes from apt, always.
- Create the venv only from `/usr/bin/python3`, never a conda/pyenv interpreter.
- Do not add `opencv-python` to `requirements.txt`; mediapipe already ships
  `opencv-contrib-python` and two cv2 providers in one venv will fight.

## The `--system-site-packages` trap (why requirements.txt pins odd packages)

During the first install, `pip install mediapipe` left mediapipe's *unpinned*
dependency `matplotlib` "already satisfied" by apt's matplotlib 3.6.3 — which
is compiled against numpy 1.x — while the venv had numpy 2.x. Result on
`import mediapipe`:

    ImportError: numpy.core.multiarray failed to import
    (A module compiled using NumPy 1.x cannot be run in NumPy 2.x)

And the same trap was waiting one level deeper in `contourpy` (also a C
extension dependency of matplotlib).

Rule going forward: **any dependency of mediapipe that also exists as an apt
package must be listed explicitly and pinned in `requirements.txt`** so the
venv owns its own copy. That is why `matplotlib` and `contourpy` sit next to
mediapipe in that file.

Known benign warning (safe to ignore):

    Unable to import Axes3D ... multiple versions of Matplotlib being installed

It is cosmetic fallout of apt's matplotlib + venv's matplotlib coexisting; this
project never uses 3D projections.

## Diagnostic cheatsheet

| Symptom                                   | Cause                          | Fix                                     |
|-------------------------------------------|--------------------------------|-----------------------------------------|
| `ModuleNotFoundError: rclpy`              | ROS 2 not sourced              | `source /opt/ros/jazzy/setup.bash`      |
| `ModuleNotFoundError: mediapipe`          | venv not active / wrong python | run via `scripts/run.sh`                |
| `cv2` imports from `/opt/ros/…`           | venv not active                | run via `scripts/run.sh`                |

## Incident log

- **2026-10-17 — "held broken packages" for the Gazebo chain.**
  This machine's `/etc/apt/sources.list.d/ubuntu.sources` was missing the
  `noble-updates` suite, so installed packages (`krb5` …, `libbsd0`) were
  *newer than anything apt could see*, making Gazebo's `-dev` dependencies
  unsatisfiable. Fix: restore `Suites: noble noble-updates`. Lesson: keep the
  standard Ubuntu pockets enabled.
- **2026-10-17 — `import mediapipe` crashed with `numpy.core.multiarray
  failed to import`.** apt's matplotlib (numpy 1.x ABI) shadowed pip's because
  of `--system-site-packages`; fixed by explicitly installing + pinning
  venv-owned `matplotlib` and `contourpy`. See the section above.
