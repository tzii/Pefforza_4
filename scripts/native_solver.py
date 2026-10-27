"""Thin wrapper around Pascal Pons' native Connect Four solver (offline tooling only).

The reference solver (https://github.com/PascalPons/connect4, AGPL-3.0) is
used to *generate* data that ships with Pefforza - the opening book and the
oracle evaluation set - and is never a runtime dependency. Build it once::

    git clone https://github.com/PascalPons/connect4
    cd connect4
    g++ -std=c++11 -O3 -DNDEBUG main.cpp Solver.cpp -o c4solver
    # no compiler? `pip install ziglang` and use `python -m ziglang c++ ...`

and download its opening book (``7x6.book``, from the repository's
releases) next to the binary, otherwise early positions take minutes each.

Scores follow the solver's convention, from the side to move: ``0`` is a
draw, a positive score ``s`` wins with ``s`` of the mover's stones still in
hand at the end (larger = faster win), negative scores lose. Columns are
zero-based in Pefforza and one-based on the solver's command line.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

INVALID = -1000


def moves_to_text(moves: Sequence[int]) -> str:
    return "".join(str(c + 1) for c in moves)


class NativeSolver:
    """A persistent ``c4solver -a`` process answering one position per line."""

    def __init__(self, binary: Path | str, book: Path | str | None = None) -> None:
        binary = Path(binary)
        if book is None:
            book = binary.with_name("7x6.book")
        self._proc = subprocess.Popen(
            [str(binary), "-a", "-b", str(book)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            cwd=binary.parent,
        )

    def analyze(self, moves: Sequence[int]) -> list[int]:
        """Exact score of each column (``INVALID`` for full columns).

        The position must be non-terminal: the solver refuses sequences in
        which a move completes a connect four.
        """
        text = moves_to_text(moves)
        assert self._proc.stdin is not None and self._proc.stdout is not None
        self._proc.stdin.write(text + "\n")
        self._proc.stdin.flush()
        line = self._proc.stdout.readline().split()
        if not text:
            # The solver echoes the (empty) sequence, so only scores remain.
            fields = line
        else:
            if not line or line[0] != text:
                raise RuntimeError(f"solver rejected position {text!r}: {line!r}")
            fields = line[1:]
        scores = [int(v) for v in fields]
        if len(scores) != 7:
            raise RuntimeError(f"unexpected solver output for {text!r}: {line!r}")
        return scores

    def analyze_many(self, positions: Iterable[Sequence[int]]) -> list[list[int]]:
        return [self.analyze(p) for p in positions]

    def close(self) -> None:
        if self._proc.stdin is not None:
            self._proc.stdin.close()
        self._proc.wait(timeout=10)

    def __enter__(self) -> NativeSolver:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
