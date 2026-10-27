"""Console entrypoints for Pefforza.

The ``[project.scripts]`` table in ``pyproject.toml`` points here:

* ``pefforza-cli`` -> :func:`pefforza.cli.play_cli.main`
* ``pefforza-gui`` -> :func:`pefforza.cli.play_gui.main`
* ``pefforza-physical`` -> :func:`pefforza.cli.play_physical.main` (needs a webcam;
  ``--watch`` gives the continuously-watching mode of the repo-root ``main.py``)

The repo-root ``play_*.py`` and ``main.py`` files are thin compatibility shims
so ``python play_cli.py``-style invocations keep working.
"""
