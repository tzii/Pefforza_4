// Browser-only demonstration. Geometry is exported from pefforza/constants.py.
// This bounded search is independent of the full Python solver and PPO model.
import geometry from './geometry.json';

export const { rows, cols, winLength, empty, ai, human, windows } = geometry;
export type Board = number[];
export type Difficulty = 'easy' | 'medium' | 'hard';
export const newBoard = (): Board => Array(rows * cols).fill(empty);
export const legalColumns = (board: Board): number[] =>
  Array.from({ length: cols }, (_, c) => c).filter((c) => board[c] === empty);

export function winningCells(board: Board): number[] {
  return (
    windows.find(
      (line) =>
        board[line[0]] !== empty &&
        line.every((i) => board[i] === board[line[0]]),
    ) ?? []
  );
}

export function winner(board: Board): number {
  const line = winningCells(board);
  return line.length ? board[line[0]] : empty;
}

export function drop(
  board: Board,
  column: number,
  player: number,
): Board | null {
  if (
    !Number.isInteger(column) ||
    column < 0 ||
    column >= cols ||
    board[column] !== empty ||
    winner(board)
  )
    return null;
  for (let r = rows - 1; r >= 0; r--) {
    const i = r * cols + column;
    if (board[i] === empty) {
      const next = [...board];
      next[i] = player;
      return next;
    }
  }
  return null;
}

const centerOrder = Array.from({ length: cols }, (_, c) => c).sort(
  (a, b) => Math.abs(a - (cols - 1) / 2) - Math.abs(b - (cols - 1) / 2),
);

function evaluate(board: Board): number {
  let score = 0;
  for (const line of windows) {
    const own = line.filter((i) => board[i] === ai).length;
    const other = line.filter((i) => board[i] === human).length;
    if (!other) score += [0, 1, 9, 70, 100000][own] ?? 0;
    if (!own) score -= [0, 1, 12, 90, 100000][other] ?? 0;
  }
  for (let r = 0; r < rows; r++) {
    const value = board[r * cols + Math.floor(cols / 2)];
    score += value === ai ? 5 : value === human ? -5 : 0;
  }
  return score;
}

export function chooseMove(
  board: Board,
  difficulty: Difficulty,
  random = Math.random,
): number | null {
  if (winner(board)) return null;
  const legal = centerOrder.filter((c) => board[c] === empty);
  if (!legal.length) return null;
  if (difficulty === 'easy')
    return legal[
      Math.min(legal.length - 1, Math.floor(random() * legal.length))
    ];
  for (const player of [ai, human]) {
    for (const column of legal) {
      const next = drop(board, column, player);
      if (next && winner(next) === player) return column;
    }
  }
  let nodes = 0;
  const budget = 16000;
  function search(
    position: Board,
    depth: number,
    maximizing: boolean,
    alpha: number,
    beta: number,
  ): number {
    const won = winner(position);
    if (won) return won === ai ? 100000 + depth : -100000 - depth;
    const available = centerOrder.filter((c) => position[c] === empty);
    if (!available.length) return 0;
    if (!depth || ++nodes > budget) return evaluate(position);
    let best = maximizing ? -Infinity : Infinity;
    for (const c of available) {
      const child = drop(position, c, maximizing ? ai : human)!;
      const value = search(child, depth - 1, !maximizing, alpha, beta);
      if (maximizing) {
        best = Math.max(best, value);
        alpha = Math.max(alpha, best);
      } else {
        best = Math.min(best, value);
        beta = Math.min(beta, best);
      }
      if (beta <= alpha) break;
    }
    return best;
  }
  let bestScore = -Infinity;
  let bestMove = legal[0];
  for (const column of legal) {
    const value = search(
      drop(board, column, ai)!,
      difficulty === 'hard' ? 4 : 0,
      false,
      -Infinity,
      Infinity,
    );
    if (value > bestScore) {
      bestScore = value;
      bestMove = column;
    }
  }
  return bestMove;
}
