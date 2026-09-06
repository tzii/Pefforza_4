"""PR5 tests: the exact-solver ``impossible`` tier and its opening strategy.

Covers the anytime ``solve_root`` provenance contract (proven win / draw /
loss, timeout fallback that never returns a refuted move), the deterministic
tactically-safe fallback, the scaled opening probe, and the tier wiring in
the difficulty registry. Timeout paths are exercised with a scripted search
- never with real timing.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from pefforza.agent.difficulty import (
    EXACT_SOLVE_MIN_PLIES,
    build_opponent,
    exact_agent,
)
from pefforza.agent.search import (
    BitPosition,
    PerfectSearchTimeoutError,
    PerfectSolver,
    opening_fallback_move,
)
from pefforza.agent.search.bitboard import (
    COLUMN_MASKS,
    MOVE_ORDER,
    compute_winning_positions,
)
from pefforza.constants import COLS
from pefforza.rules import empty_board, next_open_row

# Late-game positions with independently verified strong scores
# (cross-checked against a brute-force reference during development).
KNOWN_WIN = "12653346553665641172561773334152"  # strong score +1
KNOWN_DRAW = "11147773432527414565547711452253"  # strong score 0
KNOWN_LOSS = "4322644436262111677772276567334"  # strong score -3


def _from_moves(digits: str) -> BitPosition:
    return BitPosition.from_moves(int(ch) - 1 for ch in digits)


def _quiet_positions(seed: int = 7, count: int = 8) -> list[BitPosition]:
    """Deep, tactically open positions (>= 16 plies) for fallback checks."""
    rng = random.Random(seed)
    out: list[BitPosition] = []
    while len(out) < count:
        pos = BitPosition.empty()
        for _ in range(rng.randint(16, 24)):
            legal = pos.legal_columns(center_first=False)
            if not legal:
                break
            pos = pos.played(rng.choice(legal))
            if pos.previous_player_won:
                break
        if pos.previous_player_won or pos.is_full:
            continue
        if pos.winning_moves_mask() or pos.non_losing_moves_mask() == 0:
            continue
        out.append(pos)
    return out


class _ScriptedRootSolver(PerfectSolver):
    """Overrides the root-level search with scripted outcomes.

    ``script`` maps a root column to the value the child search should
    report (from the child's perspective) or the string "timeout". Deeper
    searches would defeat the purpose, so every root child resolves
    immediately; no real timing is involved.
    """

    def __init__(self, root: BitPosition, script: dict[int, int | str]) -> None:
        super().__init__(table_size_bits=8)
        self._children = {root.played(c).key: c for c in root.legal_columns(center_first=False)}
        self._script = script

    def _negamax(self, position: BitPosition, alpha: int, beta: int) -> int:
        col = self._children.get(position.key)
        if col is None:
            return super()._negamax(position, alpha, beta)
        outcome = self._script[col]
        if outcome == "timeout":
            raise PerfectSearchTimeoutError("scripted timeout")
        return int(outcome)


# ------------------------------------------------------------ opening fallback
def test_opening_fallback_on_empty_board_is_center():
    assert opening_fallback_move(BitPosition.empty()) == COLS // 2


def test_opening_fallback_takes_an_immediate_win():
    pos = BitPosition.from_moves([0, 6, 0, 6, 0, 6])  # red three-stack col 0
    assert opening_fallback_move(pos) == 0


def test_opening_fallback_never_gifts_a_win():
    for pos in _quiet_positions():
        move = opening_fallback_move(pos)
        child = pos.played(move)
        assert child.winning_moves_mask() == 0


# ------------------------------------------------------------------ solve_root
def test_solve_root_takes_immediate_win():
    pos = BitPosition.from_moves([0, 6, 0, 6, 0, 6])
    result = PerfectSolver(table_size_bits=14).solve_root(pos, time_budget=5)
    assert result.move == 0
    assert result.outcome == "win_now"
    assert result.proven


def test_solve_root_proves_the_known_win():
    result = PerfectSolver(table_size_bits=14).solve_root(_from_moves(KNOWN_WIN), time_budget=5)
    assert result.outcome in {"win_now", "proven_win"}
    assert result.proven


def test_solve_root_proves_the_known_draw():
    result = PerfectSolver(table_size_bits=14).solve_root(_from_moves(KNOWN_DRAW), time_budget=5)
    assert result.outcome == "proven_draw"
    assert result.proven


def test_solve_root_reports_the_known_loss():
    result = PerfectSolver(table_size_bits=14).solve_root(_from_moves(KNOWN_LOSS), time_budget=5)
    assert result.outcome == "all_lost"
    assert result.proven
    assert 0 <= result.move < COLS


def test_solve_root_falls_back_under_a_tiny_budget():
    pos = _quiet_positions()[0]
    result = PerfectSolver(table_size_bits=14).solve_root(pos, time_budget=1e-9)
    assert result.outcome == "fallback"
    assert not result.proven
    # The fallback must still be safe: no immediate win for the opponent.
    assert pos.played(result.move).winning_moves_mask() == 0


def test_solve_root_is_deterministic_on_provable_positions():
    pos = _from_moves(KNOWN_DRAW)
    a = PerfectSolver(table_size_bits=14).solve_root(pos, time_budget=5)
    b = PerfectSolver(table_size_bits=14).solve_root(pos, time_budget=5)
    assert (a.move, a.outcome, a.nodes) == (b.move, b.outcome, b.nodes)


# --------------------------------------------------- timeout-path regression
def _root_order(pos: BitPosition) -> list[int]:
    """Mirror of ``PerfectSolver._ordered_columns`` (no TT hint): the scripted
    tests need to know which root move is searched first."""
    safe = pos.non_losing_moves_mask()
    cols = [c for c in MOVE_ORDER if safe & COLUMN_MASKS[c]]

    def spots(col: int) -> int:
        bit = pos.move_bit(col)
        return compute_winning_positions(pos.current | bit, pos.mask | bit).bit_count()

    cols.sort(key=spots, reverse=True)  # stable: ties keep center-first order
    return cols


def test_timeout_never_returns_a_refuted_root_move():
    """Regression for the PR5 review bug: on timeout the fallback was
    ``ordered[0]``, which could be a root move already *proven losing*.

    Scripted: every root child is a proven loss except one, whose search
    times out. The only unresolved move is the survivor, so the fallback
    must be it - never a refuted column, whatever the ordering.
    """
    pos = _quiet_positions()[0]
    legal = pos.legal_columns(center_first=False)
    assert len(legal) >= 3
    survivor = legal[2]
    script: dict[int, int | str] = {col: ("timeout" if col == survivor else 1) for col in legal}
    result = _ScriptedRootSolver(pos, script).solve_root(pos, time_budget=1.0)
    assert result.outcome == "fallback"
    assert not result.proven
    assert result.move == survivor


def test_refuted_then_timeout_returns_first_unresolved():
    """The exact scenario from the review: the first searched root move is
    refuted (proven loss), the second times out. The fallback must be the
    first *unresolved* move - never the refuted one."""
    pos = next(p for p in _quiet_positions() if len(_root_order(p)) >= 3)
    order = _root_order(pos)
    assert len(order) >= 3
    script: dict[int, int | str] = {
        col: (1 if i != 1 else "timeout") for i, col in enumerate(order)
    }
    result = _ScriptedRootSolver(pos, script).solve_root(pos, time_budget=1.0)
    assert result.outcome == "fallback"
    # The interrupted move stays unresolved and is preferred over every
    # refuted one; the refuted order[0] must never come back.
    assert result.move == order[1]
    assert result.move != order[0]


def test_timeout_prefers_proven_draw_over_unresolved():
    """Every root move is a proven draw except the last one searched, which
    times out: the proven draw found before the deadline must be returned
    rather than the unresolved survivor."""
    pos = next(p for p in _quiet_positions() if len(_root_order(p)) >= 3)
    order = _root_order(pos)
    assert len(order) >= 3
    survivor = order[-1]
    script: dict[int, int | str] = {col: ("timeout" if col == survivor else 0) for col in order}
    result = _ScriptedRootSolver(pos, script).solve_root(pos, time_budget=1.0)
    assert result.outcome == "proven_draw"
    assert result.proven
    assert result.move != survivor


# ------------------------------------------------------------- tier wiring
def test_impossible_tier_blocks_an_immediate_threat():
    agent = build_opponent("impossible", seed=0)
    board = empty_board()
    for c in (0, 1, 2):  # human (P1) three in a row; AI (P2) must block
        board[next_open_row(board, c), c] = 1
    valid = [c for c in range(COLS) if board[0, c] == 0]
    assert agent(board, 2, valid) == 3


def test_impossible_tier_takes_an_immediate_win():
    agent = build_opponent("impossible", seed=0)
    board = empty_board()
    for c, player in ((0, 2), (6, 1), (0, 2), (6, 1), (0, 2), (6, 1)):
        board[next_open_row(board, c), c] = player
    valid = [c for c in range(COLS) if board[0, c] == 0]
    assert agent(board, 2, valid) == 0


def test_impossible_opening_probe_returns_center_quickly():
    """Shallow positions are probed cheaply (never the full budget): on an
    empty board the probe cannot prove anything, so the deterministic
    fallback answers with the center column."""
    agent = exact_agent(time_budget=30.0)  # full budget would be huge - probe wins
    board = empty_board()
    valid = list(range(COLS))
    assert agent(board, 1, valid) == COLS // 2


def test_opening_probe_still_proves_cheap_shallow_positions(monkeypatch):
    """A shallow position whose proof fits the probe budget must get the
    proven move, not the fallback - "proven-optimal whenever the proof
    fits" includes sub-floor positions (PR5 review finding). The probe
    budget is raised via monkeypatch so the assertion is structural, not
    a race against CI hardware."""
    import pefforza.agent.difficulty as difficulty_module

    sequence = [3, 4, 1, 4, 3, 0, 2, 1, 1, 5, 1, 5, 6]
    pos = BitPosition.from_moves(sequence)
    assert pos.moves < EXACT_SOLVE_MIN_PLIES
    board = pos.to_board()

    expected = PerfectSolver(table_size_bits=21).solve_root(pos, time_budget=2.0)
    assert expected.outcome == "proven_win"

    monkeypatch.setattr(difficulty_module, "OPENING_PROBE_BUDGET", 2.0)
    agent = exact_agent(time_budget=30.0)  # full budget irrelevant: probe path
    assert agent(board, pos.to_move, list(range(COLS))) == expected.move


def test_impossible_floor_constant_covers_the_deep_opening():
    # The floor must sit deep enough that no known-weak-solvable position is
    # below it: sanity-check it against the documented benchmark boundary.
    assert EXACT_SOLVE_MIN_PLIES >= 12
    assert EXACT_SOLVE_MIN_PLIES < 20


def test_exact_agent_plays_proven_optimal_above_the_floor():
    """Above the floor the tier's move must preserve the game value."""
    pos = _from_moves(KNOWN_WIN)  # to-move player has a forced win
    assert pos.moves >= EXACT_SOLVE_MIN_PLIES
    board = pos.to_board()
    agent = exact_agent(time_budget=5)
    move = agent(board, pos.to_move, [c for c in range(COLS) if board[0, c] == 0])
    child = BitPosition.from_board(board, to_move=pos.to_move).played(move)
    # The chosen move keeps the forced win: the opponent now stands lost.
    assert PerfectSolver(table_size_bits=14).solve(child, weak=True).score == -1


def test_exact_agent_fallback_respects_column_mask():
    """When the chosen column is somehow not in the caller's valid list, the
    agent must still return a legal fallback (defense-in-depth contract)."""
    agent = exact_agent(time_budget=0.05)
    board = empty_board()
    assert agent(board, 1, [2]) == 2


def test_dunder_version_matches_installed_metadata():
    from importlib.metadata import version

    import pefforza

    assert pefforza.__version__ == version("pefforza")


def test_exact_root_rejects_finished_wins():
    position = BitPosition.from_moves([0, 6, 1, 6, 2, 6, 3])
    with pytest.raises(ValueError, match="terminal"):
        PerfectSolver(table_size_bits=8).solve_root(position)
    assert opening_fallback_move(position) == -1


def test_exact_root_reports_full_board_as_a_draw():
    board = np.array(
        [[1, 1, 2, 2, 1, 1, 2], [2, 2, 1, 1, 2, 2, 1]] * 3,
        dtype=np.int8,
    )
    position = BitPosition.from_board(board, to_move=1)
    assert position.is_full and not position.previous_player_won
    result = PerfectSolver(table_size_bits=8).solve_root(position)
    assert (result.move, result.outcome, result.proven) == (-1, "proven_draw", True)


def test_opening_probe_honors_a_smaller_caller_budget(monkeypatch):
    budgets = []

    def solve_root(self, position, *, time_budget):
        from pefforza.agent.search.perfect import RootResult

        budgets.append(time_budget)
        return RootResult(3, "fallback", False, 0, 0)

    monkeypatch.setattr(PerfectSolver, "solve_root", solve_root)
    agent = exact_agent(time_budget=0.001)
    assert agent(empty_board(), 1, list(range(COLS))) == 3
    assert budgets == [0.001]
