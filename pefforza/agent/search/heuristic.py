"""Static evaluation operating directly on bitboards.

The weights intentionally match :func:`pefforza.agent.minimax.evaluate_position`
so performance/correctness comparisons isolate the board representation rather
than silently changing playing style.
"""

from __future__ import annotations

from pefforza.constants import COLS, ROWS, WIN_LENGTH

from .bitboard import CENTER_MASK, BitPosition, bit_for_cell


def _window_masks() -> tuple[int, ...]:
    masks: list[int] = []

    for r in range(ROWS):
        for c in range(COLS - WIN_LENGTH + 1):
            masks.append(sum(bit_for_cell(r, c + i) for i in range(WIN_LENGTH)))

    for c in range(COLS):
        for r in range(ROWS - WIN_LENGTH + 1):
            masks.append(sum(bit_for_cell(r + i, c) for i in range(WIN_LENGTH)))

    for r in range(ROWS - WIN_LENGTH + 1):
        for c in range(COLS - WIN_LENGTH + 1):
            masks.append(sum(bit_for_cell(r + i, c + i) for i in range(WIN_LENGTH)))

    for r in range(WIN_LENGTH - 1, ROWS):
        for c in range(COLS - WIN_LENGTH + 1):
            masks.append(sum(bit_for_cell(r - i, c + i) for i in range(WIN_LENGTH)))

    return tuple(masks)


WINDOW_MASKS = _window_masks()


def evaluate_bit_position(position: BitPosition) -> int:
    """Match the legacy matrix heuristic from the current player's view."""
    own = position.current
    opp = position.opponent
    score = 3 * (own & CENTER_MASK).bit_count()

    for window in WINDOW_MASKS:
        p = (own & window).bit_count()
        o = (opp & window).bit_count()
        e = WIN_LENGTH - p - o

        if p == 4:
            score += 100
        elif p == 3 and e == 1:
            score += 5
        elif p == 2 and e == 2:
            score += 2
        elif o == 3 and e == 1:
            score -= 4

    return score


__all__ = ["WINDOW_MASKS", "evaluate_bit_position"]
