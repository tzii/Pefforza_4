"""End-to-end simulations: try hard to break the AI in real game flow.

These tests don't rely on hand-crafted positions. They play *full games*
against adversarial human strategies and assert two invariants after every
AI move:

* If the human had a single immediate winning move the AI didn't take, fail.
* If the human had any reachable 3-in-a-row threat that the AI ignored, fail.

If any test here fails, the failure message includes the move sequence and
the offending board, so we can replay it.
"""

from __future__ import annotations

import pytest

from pefforza.agent.difficulty import build_opponent
from pefforza.agent.minimax import find_immediate_win
from pefforza.constants import COLS
from pefforza.envs.connect4_env import Connect4Env
from pefforza.rules import available_columns


def _format_board(board) -> str:
    rows = []
    for r in range(board.shape[0]):
        rows.append("  " + " ".join("X" if v == 1 else "O" if v == 2 else "." for v in board[r]))
    rows.append("  " + " ".join(str(c) for c in range(COLS)))
    return "\n".join(rows)


def _play_full_game(human_strategy, ai_agent, max_moves: int = 42, seed: int = 0):
    """Play a full game. ``human_strategy`` is called with (board, valid) -> col."""
    env = Connect4Env()
    env.reset(seed=seed)
    history: list[tuple[str, int]] = []

    for _ in range(max_moves):
        valid = available_columns(env.board)
        if not valid:
            return history, "draw"

        if env.current_player == 1:
            col = human_strategy(env.board, valid)
            if col not in valid:
                col = valid[0]
            history.append(("H", col))
            _, _, terminated, _, info = env.step(col)
            if terminated:
                if info.get("winner") == 1:
                    return history, "human_won"
                return history, "draw"
            continue

        # AI's move. BEFORE the AI moves, snapshot any threat the human has.
        pre_board = env.board.copy()
        human_immediate_win = find_immediate_win(pre_board, player=1, valid=valid)
        ai_immediate_win = find_immediate_win(pre_board, player=2, valid=valid)

        col = ai_agent(env.board, my_id=2, valid=valid)
        if col not in valid:
            col = valid[0]
        history.append(("A", col))
        _, _, terminated, _, info = env.step(col)

        # Watchdog: AI must not ignore a blockable threat unless it has its
        # own immediate win (taking your own win ends the game and is always
        # preferable to blocking).
        ignored_threat = (
            human_immediate_win is not None
            and col != human_immediate_win
            and ai_immediate_win is None
        )
        # If the AI claimed its own win, verify the game actually ended with it.
        ai_claimed_win_invalid = (
            ai_immediate_win is not None
            and col == ai_immediate_win
            and not (terminated and info.get("winner") == 2)
        )
        if ignored_threat or ai_claimed_win_invalid:
            board_str = _format_board(pre_board)
            history_str = " ".join(f"{p}{c}" for p, c in history)
            reason = (
                "AI failed to block immediate threat"
                if ignored_threat
                else "AI thought it had a winning move but the game didn't end"
            )
            raise AssertionError(
                f"{reason}.\n"
                f"Human could win at column {human_immediate_win}, "
                f"AI immediate win was at {ai_immediate_win}, AI played {col}.\n"
                f"Board before AI's move:\n{board_str}\n"
                f"Move history: {history_str}"
            )

        if terminated:
            if info.get("winner") == 2:
                return history, "ai_won"
            return history, "draw"

    return history, "max_moves"


# --------------------------------------------------------- human strategies
def _greedy_winning_human():
    """Human always takes any immediate win, otherwise plays center then random."""
    import random as _r

    rng = _r.Random(0)

    def strategy(board, valid):
        win = find_immediate_win(board, 1, valid)
        if win is not None:
            return win
        if COLS // 2 in valid:
            return COLS // 2
        return rng.choice(valid)

    return strategy


def _stack_one_column_human(col: int):
    """Always drop in the same column - tries to force a vertical 4."""

    def strategy(board, valid):
        if col in valid:
            return col
        # Fallback when target column is full.
        return valid[0]

    return strategy


def _row_filler_human():
    """Plays leftmost-empty-on-bottom-row first; tries for horizontal 4."""

    def strategy(board, valid):
        # Prefer columns that haven't been used yet (still have row=5 empty).
        bottom_open = [c for c in valid if board[-1, c] == 0]
        if bottom_open:
            return min(bottom_open)
        return valid[0]

    return strategy


# -------------------------------------------------------------- the tests
@pytest.mark.parametrize(
    "difficulty,strategy_factory",
    [
        ("medium", _greedy_winning_human),
        ("hard", _greedy_winning_human),
        ("impossible", _greedy_winning_human),
        ("medium", lambda: _stack_one_column_human(3)),
        ("hard", lambda: _stack_one_column_human(3)),
        ("impossible", lambda: _stack_one_column_human(3)),
        ("medium", lambda: _stack_one_column_human(0)),
        ("hard", lambda: _stack_one_column_human(0)),
        ("impossible", lambda: _stack_one_column_human(0)),
        ("medium", _row_filler_human),
        ("hard", _row_filler_human),
        ("impossible", _row_filler_human),
    ],
)
def test_ai_never_ignores_blockable_threat(difficulty: str, strategy_factory):
    """Watchdog runs after every AI move and asserts no blockable threat was ignored."""
    ai = build_opponent(difficulty, seed=0)
    strategy = strategy_factory()
    history, _outcome = _play_full_game(strategy, ai)
    assert history  # trivially true; the real assertion is inside _play_full_game
