"""Headless evaluation harness.

Run a trained PPO checkpoint (or any difficulty tier) against canned
opponents and report win / loss / draw rates, or grade every move against the
exact oracle set (:mod:`pefforza.agent.oracle`). Useful for answering "is my
newer checkpoint actually better?" or "is ``impossible`` really perfect?"
without a webcam, GUI, or audio device.

Usage:

.. code-block:: bash

    # 100 games vs the 1-ply heuristic, half as P1, half as P2:
    python -m pefforza.agent.evaluate --games 100 --opponent heuristic

    # Compare two checkpoints head-to-head:
    python -m pefforza.agent.evaluate \\
        --model new.zip --opponent model --opponent-model old.zip --games 200
"""

from __future__ import annotations

import argparse
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pefforza.constants import COLS, DEFAULT_MODEL_PATH
from pefforza.envs.connect4_env import Connect4Env
from pefforza.rules import (
    Board,
    available_columns,
    check_winner,
    next_open_row,
    swap_perspective,
)

logger = logging.getLogger(__name__)

# An Agent is any callable that, given the current board, the player id it is
# playing as (1 or 2), and the list of legal columns, returns the column to
# drop into.
Agent = Callable[[Board, int, list[int]], int]


# ---------------------------------------------------------------- opponents
def random_agent(seed: int | None = None) -> Agent:
    """Pick a uniformly random legal column."""
    rng = random.Random(seed)

    def select(board: Board, my_id: int, valid: list[int]) -> int:
        return rng.choice(valid)

    return select


def heuristic_agent(seed: int | None = None) -> Agent:
    """1-ply lookahead: win if possible, otherwise block, otherwise prefer center."""
    rng = random.Random(seed)
    center = COLS // 2

    def _winning_move(board: Board, player: int, valid: list[int]) -> int | None:
        for c in valid:
            row = next_open_row(board, c)
            if row < 0:
                continue
            sim = board.copy()
            sim[row, c] = player
            if check_winner(sim) == player:
                return c
        return None

    def select(board: Board, my_id: int, valid: list[int]) -> int:
        win = _winning_move(board, my_id, valid)
        if win is not None:
            return win
        block = _winning_move(board, 3 - my_id, valid)
        if block is not None:
            return block
        if center in valid:
            return center
        return rng.choice(valid)

    return select


def _action_probabilities(model: object, obs: Board) -> list[float] | None:
    """Policy probabilities for every column, or None if unavailable."""
    try:
        import torch

        policy = model.policy  # type: ignore[attr-defined]
        obs_tensor, _ = policy.obs_to_tensor(obs)
        with torch.no_grad():
            probs = policy.get_distribution(obs_tensor).distribution.probs[0]
        return [float(p) for p in probs.cpu()]
    except Exception:  # not an SB3 actor-critic policy: use predict() instead
        return None


def model_agent(model: object, deterministic: bool = True) -> Agent:
    """Wrap a Stable-Baselines3 model. Translates board to the model's perspective.

    Deterministic play takes the most probable *legal* column (illegal
    columns are masked out of the policy distribution); a policy without
    accessible probabilities falls back to ``predict`` and, if that picks a
    full column, to the first legal one.
    """

    def select(board: Board, my_id: int, valid: list[int]) -> int:
        # The model was trained as player 1; if it's actually playing as 2 in
        # this game, swap so it always sees "1 = self, 2 = opponent".
        obs = board if my_id == 1 else swap_perspective(board)
        if deterministic:
            probs = _action_probabilities(model, obs)
            if probs is not None:
                return max(valid, key=lambda c: probs[c])
        action, _ = model.predict(obs, deterministic=deterministic)  # type: ignore[attr-defined]
        action = int(action)
        if action not in valid:
            logger.debug("Model picked invalid column %d, falling back.", action)
            return valid[0]
        return action

    return select


# ----------------------------------------------------------------- runner
@dataclass
class MatchResult:
    wins: int = 0
    losses: int = 0
    draws: int = 0

    @property
    def games(self) -> int:
        return self.wins + self.losses + self.draws

    @property
    def win_rate(self) -> float:
        return self.wins / self.games if self.games else 0.0

    def __str__(self) -> str:
        n = max(self.games, 1)
        return (
            f"games={self.games}  "
            f"wins={self.wins} ({100 * self.wins / n:5.1f}%)  "
            f"losses={self.losses} ({100 * self.losses / n:5.1f}%)  "
            f"draws={self.draws} ({100 * self.draws / n:5.1f}%)"
        )


def play_one_game(
    agent_a: Agent,
    agent_b: Agent,
    seed: int | None = None,
) -> int:
    """Play one game. Returns 1 if A wins, 2 if B wins, 0 if draw / forfeit."""
    env = Connect4Env()
    env.reset(seed=seed)
    while True:
        valid = available_columns(env.board)
        if not valid:
            return 0
        if env.current_player == 1:
            action = agent_a(env.board, 1, valid)
        else:
            action = agent_b(env.board, 2, valid)
        if action not in valid:
            # Treat illegal actions as a forfeit by the chooser.
            return 2 if env.current_player == 1 else 1
        _, _, terminated, _, info = env.step(action)
        if terminated:
            winner = info.get("winner")
            return int(winner) if winner is not None else 0


def evaluate(
    agent: Agent,
    opponent: Agent,
    games: int,
    seed: int | None = None,
    swap_sides: bool = True,
) -> MatchResult:
    """Run ``games`` games. Alternates first-mover by default."""
    rng = random.Random(seed)
    result = MatchResult()
    for i in range(games):
        agent_first = (i % 2 == 0) if swap_sides else True
        game_seed = rng.randint(0, 2**31 - 1)
        if agent_first:
            outcome = play_one_game(agent, opponent, seed=game_seed)
            agent_won = outcome == 1
        else:
            outcome = play_one_game(opponent, agent, seed=game_seed)
            agent_won = outcome == 2
        if outcome == 0:
            result.draws += 1
        elif agent_won:
            result.wins += 1
        else:
            result.losses += 1
    return result


# -------------------------------------------------------------------- CLI
OPPONENT_CHOICES = ("random", "heuristic", "minimax", "self", "model")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help=f"PPO checkpoint to evaluate (default: {DEFAULT_MODEL_PATH}).",
    )
    p.add_argument(
        "--difficulty",
        default=None,
        help="Evaluate a difficulty tier (easy/medium/hard/impossible/neural) instead of --model.",
    )
    p.add_argument(
        "--opponent",
        choices=OPPONENT_CHOICES,
        default="heuristic",
        help="Baseline to play against. 'self' = the evaluated agent itself, "
        "'model' = a second checkpoint via --opponent-model.",
    )
    p.add_argument(
        "--opponent-model", type=Path, default=None, help="Required when --opponent=model."
    )
    p.add_argument(
        "--minimax-depth",
        type=int,
        default=4,
        help="Search depth when --opponent=minimax (default: 4).",
    )
    p.add_argument("--games", type=int, default=100)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--oracle",
        action="store_true",
        help="Grade every move against the exact oracle set instead of playing matches.",
    )
    p.add_argument(
        "--oracle-source",
        choices=("all", "line", "random"),
        default="all",
        help="--oracle only: restrict to one population of the set (default: all).",
    )
    return p.parse_args(argv)


def _build_opponent(args: argparse.Namespace, primary: Agent) -> Agent | None:
    if args.opponent == "random":
        return random_agent(seed=args.seed)
    if args.opponent == "heuristic":
        return heuristic_agent(seed=args.seed)
    if args.opponent == "minimax":
        from pefforza.agent.minimax import minimax_agent

        return minimax_agent(depth=args.minimax_depth, seed=args.seed)
    if args.opponent == "self":
        return primary
    if args.opponent == "model":
        if args.opponent_model is None or not args.opponent_model.exists():
            logger.error("--opponent=model requires --opponent-model pointing to a real file.")
            return None
        from stable_baselines3 import PPO  # local import; optional dep

        return model_agent(PPO.load(str(args.opponent_model)))
    return None


def _build_agent(args: argparse.Namespace) -> tuple[Agent, str] | None:
    if args.difficulty is not None:
        from pefforza.agent.difficulty import DIFFICULTY_NAMES, build_opponent

        if args.difficulty not in DIFFICULTY_NAMES:
            logger.error(
                "Unknown difficulty %r. Choose from %s.", args.difficulty, DIFFICULTY_NAMES
            )
            return None
        agent = build_opponent(args.difficulty, seed=args.seed, model_path=args.model)
        return agent, args.difficulty

    if not args.model.exists():
        logger.error("Model not found: %s", args.model)
        return None
    from stable_baselines3 import PPO  # local import; optional dep

    return model_agent(PPO.load(str(args.model))), args.model.name


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args(argv)

    built = _build_agent(args)
    if built is None:
        return 2
    agent, name = built

    if args.oracle:
        from pefforza.agent.oracle import load_oracle_positions, oracle_evaluate

        positions = load_oracle_positions()
        if args.oracle_source != "all":
            positions = [p for p in positions if p.source == args.oracle_source]
        print(f"Grading {name} on {len(positions)} oracle positions ({args.oracle_source})...")
        print(oracle_evaluate(agent, positions))
        return 0

    opp = _build_opponent(args, agent)
    if opp is None:
        return 2
    label = args.opponent if args.opponent != "model" else f"model:{args.opponent_model.name}"
    print(f"Evaluating {name} vs {label} over {args.games} games (seed={args.seed})...")
    result = evaluate(agent, opp, games=args.games, seed=args.seed)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
