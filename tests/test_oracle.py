"""Exact-oracle evaluation set and grading harness."""

from __future__ import annotations

import pytest

from pefforza.agent.difficulty import exact_agent
from pefforza.agent.evaluate import heuristic_agent
from pefforza.agent.evaluate import main as evaluate_main
from pefforza.agent.oracle import (
    OraclePosition,
    load_oracle_positions,
    oracle_evaluate,
)
from pefforza.agent.search import BitPosition, default_book
from pefforza.constants import COLS, ROWS
from pefforza.rules import available_columns, check_winner


@pytest.fixture(scope="module")
def positions():
    return load_oracle_positions()


def test_grading_rules_on_a_synthetic_position():
    pos = OraclePosition(moves=(), scores=(-2, -1, 0, 1, 0, -1, -2))
    assert pos.to_move == 1
    assert pos.is_optimal(3) and pos.preserves_value(3)
    assert not pos.preserves_value(2)  # a draw squanders the win
    lost = OraclePosition(moves=(3,), scores=(-3, -2, -1, -4, -1, -2, -3))
    assert lost.to_move == 2
    assert lost.preserves_value(0) and not lost.is_optimal(0)
    assert lost.is_optimal(2) and lost.is_optimal(4)


def test_oracle_set_is_well_formed(positions):
    assert len(positions) >= 500
    assert {p.source for p in positions} == {"line", "random"}
    for pos in positions:
        board = pos.board()
        assert check_winner(board) == 0, "oracle positions must be non-terminal"
        assert len(pos.scores) == COLS
        valid = set(available_columns(board))
        assert {c for c in range(COLS) if pos.scores[c] is not None} == valid
        assert int((board != 0).sum()) == pos.ply <= ROWS * COLS - 1


def test_book_moves_match_independent_exact_scores(positions):
    """Every book answer must be exactly optimal against the oracle."""
    book = default_book()
    assert book is not None
    checked = 0
    for pos in positions:
        entry = book.lookup(BitPosition.from_moves(pos.moves))
        if entry is None:
            continue
        checked += 1
        assert pos.is_optimal(entry.move), (pos.moves, entry, pos.scores)
        assert entry.score == pos.best_score
    assert checked >= 200


def test_impossible_tier_is_perfect_on_line_positions_past_the_book(positions):
    """Endgame slice of the oracle measurement, cheap enough for every CI run;
    ``python -m pefforza.agent.evaluate --oracle --difficulty impossible``
    grades the whole set."""
    deep = [p for p in positions if p.source == "line" and p.ply >= 26]
    assert len(deep) >= 30
    report = oracle_evaluate(exact_agent(), deep)
    assert report.total.value_rate == 1.0, report.mistakes[:3]


def test_report_buckets_and_mistakes(positions):
    sample = positions[:60]
    report = oracle_evaluate(heuristic_agent(seed=0), sample)
    assert report.total.positions == len(sample)
    assert sum(b.positions for b in report.buckets.values()) == len(sample)
    assert len(report.mistakes) == report.total.positions - report.total.value_preserving
    text = str(report)
    assert "value-preserving" in text and "all" in text


def test_evaluate_cli_oracle_mode(capsys):
    assert evaluate_main(["--oracle", "--difficulty", "medium", "--oracle-source", "random"]) == 0
    out = capsys.readouterr().out
    assert "Grading medium on" in out
    assert "exactly-optimal" in out


def test_evaluate_cli_tier_match_and_bad_tier(capsys):
    assert evaluate_main(["--difficulty", "medium", "--opponent", "random", "--games", "2"]) == 0
    assert "Evaluating medium vs random" in capsys.readouterr().out
    assert evaluate_main(["--difficulty", "nope"]) == 2
