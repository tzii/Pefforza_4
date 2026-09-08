import assert from 'node:assert/strict';
import { test } from 'node:test';
import cases from './python-rules.json';
import {
  ai,
  human,
  rows,
  cols,
  drop,
  newBoard,
  legalColumns,
  winner,
  winningCells,
  chooseMove,
  windows,
  type Board,
} from '../lib/game';
import { gameReducer } from '../components/playground';

await test('browser rules match Python on 2,377 positions from 100 complete games', () => {
  for (const position of cases) {
    assert.equal(winner(position.board), position.winner);
    assert.deepEqual(legalColumns(position.board), position.legal);
  }
});

await test('every exported winning direction is recognized for both players', () => {
  for (const player of [ai, human])
    for (const line of windows) {
      const board = newBoard();
      for (const index of line) board[index] = player;
      assert.equal(winner(board), player);
      assert.equal(winningCells(board).length, line.length);
    }
});

await test('gravity, immutable moves, and illegal or full columns', () => {
  const empty = newBoard();
  const first = drop(empty, 2, human)!;
  assert.equal(first[(rows - 1) * cols + 2], human);
  assert.equal(
    empty.every((cell) => cell === 0),
    true,
  );
  for (const col of [-1, cols, 0.5, NaN])
    assert.equal(drop(empty, col, human), null);
  let board = newBoard();
  for (let r = 0; r < rows; r++) board = drop(board, 0, r % 2 ? ai : human)!;
  assert.equal(drop(board, 0, human), null);
  assert.equal(legalColumns(board).includes(0), false);
});

await test('medium and hard block a horizontal win and take their own win first', () => {
  const threat = newBoard();
  for (const col of [0, 1, 2]) threat[(rows - 1) * cols + col] = human;
  const ownWin = threat.map((value) => (value === human ? ai : value));
  for (const difficulty of ['medium', 'hard'] as const) {
    assert.equal(chooseMove(threat, difficulty), 3);
    assert.equal(chooseMove(ownWin, difficulty), 3);
    assert.equal(winner(drop(ownWin, 3, ai)!), ai);
  }
});

await test('finished games accept neither another drop nor an AI move', () => {
  const board = newBoard();
  for (const cell of windows[0]) board[cell] = human;
  assert.equal(drop(board, 6, ai), null);
  assert.equal(chooseMove(board, 'hard'), null);
  assert.equal(chooseMove(Array(rows * cols).fill(ai), 'medium'), null);
});

await test('AI remains legal through complete seeded games and fills no occupied cells', () => {
  let seed = 111;
  const random = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
  for (const difficulty of ['easy', 'medium', 'hard'] as const) {
    for (let game = 0; game < 4; game++) {
      let board: Board = newBoard();
      while (!winner(board) && legalColumns(board).length) {
        const legal = legalColumns(board);
        board = drop(board, legal[Math.floor(random() * legal.length)], human)!;
        if (winner(board) || !legalColumns(board).length) break;
        const column = chooseMove(board, difficulty, random);
        assert.ok(column !== null && legalColumns(board).includes(column));
        const next = drop(board, column, ai)!;
        assert.equal(
          next.filter(Boolean).length,
          board.filter(Boolean).length + 1,
        );
        board = next;
      }
    }
  }
});

await test('turn locking, AI failure/retry, reset, and stale replies', () => {
  const initial = {
    board: newBoard(),
    phase: 'ready' as const,
    difficulty: 'medium' as const,
    last: -1,
    round: 0,
  };
  const thinking = gameReducer(initial, { type: 'human', column: 3 });
  assert.equal(thinking.phase, 'thinking');
  assert.equal(gameReducer(thinking, { type: 'human', column: 2 }), thinking);
  const failed = gameReducer(thinking, { type: 'error' });
  assert.equal(failed.phase, 'error');
  assert.equal(gameReducer(failed, { type: 'retry' }).phase, 'thinking');
  const reply = gameReducer(thinking, { type: 'ai', column: 2 });
  assert.equal(reply.phase, 'ready');
  assert.equal(reply.board.filter(Boolean).length, 2);
  const reset = gameReducer(thinking, { type: 'reset', difficulty: 'hard' });
  assert.equal(reset.difficulty, 'hard');
  assert.equal(reset.round, 1);
  assert.equal(reset.board.filter(Boolean).length, 0);
  assert.equal(gameReducer(reset, { type: 'ai', column: 1 }), reset);
});
