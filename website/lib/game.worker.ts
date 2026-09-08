import { chooseMove, type Board, type Difficulty } from './game';

self.onmessage = (
  event: MessageEvent<{ board: Board; difficulty: Difficulty }>,
) => {
  try {
    self.postMessage({
      column: chooseMove(event.data.board, event.data.difficulty),
    });
  } catch {
    self.postMessage({
      error: 'The browser opponent could not calculate a move.',
    });
  }
};
