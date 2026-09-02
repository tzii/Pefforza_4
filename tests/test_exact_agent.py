"""PR5 tests: the exact-solver ``impossible`` tier and its opening strategy.

Covers the anytime ``solve_root`` provenance contract (proven win / draw /
loss, timeout fallback), the deterministic opening fallback, and the tier
wiring in the difficulty registry. All positions are chosen so proofs are
machine-independent: immediate tactics, late-game solves that take
milliseconds, and fallbacks with budgets that always expire.
"""

from __future__ import annotations

import random

from pefforza.agent.difficulty import (
    EXACT_SOLVE_MIN_PLIES,
    build_opponent,
    exact_agent,
)
from pefforza.agent.search import BitPosition, PerfectSolver, opening_fallback_move
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


def test_impossible_opening_floor_is_instant_and_center_first():
    """Below the exact-solve floor the tier answers immediately (no budget
    burned) with the deterministic opening fallback."""
    agent = exact_agent(time_budget=30.0)  # budget would be huge - floor wins
    board = empty_board()
    valid = list(range(COLS))
    assert agent(board, 1, valid) == COLS // 2


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
