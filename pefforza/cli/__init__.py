"""Console entrypoints for Pefforza.

The ``[project.scripts]`` table in ``pyproject.toml`` points here:

* ``pefforza-cli`` -> :func:`pefforza.cli.play_cli.main`
* ``pefforza-gui`` -> :func:`pefforza.cli.play_gui.main`

``play_physical`` ships as a module (``python -m pefforza.cli.play_physical``)
rather than a console script because it requires a webcam. The repo-root
``play_*.py`` files are thin compatibility shims so ``python play_cli.py``-style
invocations keep working.
"""
