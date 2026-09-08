'use client';

import { useCallback, useEffect, useReducer, useRef } from 'react';
import { ArrowDown, ArrowUpRight, RotateCcw, Sparkles } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  ai,
  cols,
  drop,
  empty,
  human,
  legalColumns,
  newBoard,
  rows,
  winner,
  winningCells,
  type Board,
  type Difficulty,
} from '@/lib/game';

type Phase = 'ready' | 'thinking' | 'finished' | 'error';
type State = {
  board: Board;
  phase: Phase;
  difficulty: Difficulty;
  last: number;
  round: number;
};
type Action =
  | { type: 'human' | 'ai'; column: number }
  | { type: 'reset'; difficulty?: Difficulty }
  | { type: 'error' | 'retry' };
const initial: State = {
  board: newBoard(),
  phase: 'ready',
  difficulty: 'medium',
  last: -1,
  round: 0,
};

export function gameReducer(state: State, action: Action): State {
  if (action.type === 'reset')
    return {
      ...initial,
      board: newBoard(),
      difficulty: action.difficulty ?? state.difficulty,
      round: state.round + 1,
    };
  if (action.type === 'error')
    return state.phase === 'thinking' ? { ...state, phase: 'error' } : state;
  if (action.type === 'retry')
    return state.phase === 'error' ? { ...state, phase: 'thinking' } : state;
  if (!('column' in action)) return state;
  if (action.type === 'human' && state.phase !== 'ready') return state;
  if (action.type === 'ai' && state.phase !== 'thinking') return state;
  const board = drop(
    state.board,
    action.column,
    action.type === 'human' ? human : ai,
  );
  if (!board) return state;
  const finished = !!winner(board) || !legalColumns(board).length;
  return {
    ...state,
    board,
    last: board.findIndex((value, i) => value !== state.board[i]),
    phase: finished
      ? 'finished'
      : action.type === 'human'
        ? 'thinking'
        : 'ready',
  };
}

export function Playground() {
  const [state, dispatch] = useReducer(gameReducer, initial);
  const { board, phase, difficulty, last } = state;
  const stateRef = useRef(state);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);
  const win = winner(board);
  const line = winningCells(board);
  const moveCount = board.filter((value) => value !== empty).length;
  const play = useCallback(
    (column: number) => dispatch({ type: 'human', column }),
    [],
  );

  useEffect(() => {
    if (phase !== 'thinking') return;
    let worker: Worker | undefined;
    let responseTimer: ReturnType<typeof setTimeout> | undefined;
    const began = performance.now();
    const deadline = setTimeout(() => {
      worker?.terminate();
      dispatch({ type: 'error' });
    }, 12000);
    try {
      worker = new Worker(new URL('../lib/game.worker.ts', import.meta.url), {
        type: 'module',
      });
      worker.onmessage = (event) => {
        clearTimeout(deadline);
        if (
          event.data.error ||
          !Number.isInteger(event.data.column) ||
          !legalColumns(board).includes(event.data.column)
        ) {
          dispatch({ type: 'error' });
          return;
        }
        responseTimer = setTimeout(
          () => dispatch({ type: 'ai', column: event.data.column }),
          Math.max(0, 450 - (performance.now() - began)),
        );
      };
      worker.onerror = () => {
        clearTimeout(deadline);
        dispatch({ type: 'error' });
      };
      worker.postMessage({ board, difficulty });
    } catch {
      clearTimeout(deadline);
      dispatch({ type: 'error' });
    }
    return () => {
      worker?.terminate();
      clearTimeout(deadline);
      clearTimeout(responseTimer);
    };
  }, [board, difficulty, phase]);

  useEffect(() => {
    type Tool = {
      name: string;
      description: string;
      inputSchema: object;
      annotations: { readOnlyHint: boolean };
      execute: (input: unknown) => unknown;
    };
    const context = (
      document as Document & {
        modelContext?: {
          registerTool: (
            tool: Tool,
            options: { signal: AbortSignal },
          ) => void | Promise<void>;
        };
      }
    ).modelContext;
    if (!context) return;
    const lifecycle = new AbortController();
    const register = (tool: Tool) => {
      try {
        void Promise.resolve(
          context.registerTool(tool, { signal: lifecycle.signal }),
        ).catch(() => {});
      } catch {
        /* Optional browser integration; the game remains usable. */
      }
    };
    register({
      name: 'read_pefforza_game',
      description:
        'Read the current browser demo board, player turn, difficulty, and legal columns (1-based).',
      inputSchema: {
        type: 'object',
        properties: {},
        additionalProperties: false,
      },
      annotations: { readOnlyHint: true },
      execute: () => ({
        ...stateRef.current,
        legalColumns: legalColumns(stateRef.current.board).map((c) => c + 1),
        winner: winner(stateRef.current.board),
      }),
    });
    register({
      name: 'play_pefforza_column',
      description:
        'Drop the human red disc into a legal column (1–7) in the visible browser game. This starts the AI reply.',
      inputSchema: {
        type: 'object',
        properties: { column: { type: 'integer', minimum: 1, maximum: cols } },
        required: ['column'],
        additionalProperties: false,
      },
      annotations: { readOnlyHint: false },
      execute: async (input) => {
        const column = (input as { column?: unknown })?.column;
        if (
          typeof column !== 'number' ||
          !Number.isInteger(column) ||
          column < 1 ||
          column > cols
        )
          throw new Error('Choose a column from 1 to 7.');
        if (
          stateRef.current.phase !== 'ready' ||
          !legalColumns(stateRef.current.board).includes(column - 1)
        )
          throw new Error('That move is not available.');
        play(column - 1);
        await new Promise<void>((resolve) =>
          requestAnimationFrame(() => resolve()),
        );
        return { board: stateRef.current.board, phase: stateRef.current.phase };
      },
    });
    return () => lifecycle.abort();
  }, [play]);

  const message =
    phase === 'error'
      ? 'The opponent paused.'
      : phase === 'thinking'
        ? 'A little thinking. A little plotting.'
        : win === human
          ? 'Well played. You connected four.'
          : win === ai
            ? 'Four in a row. The machine takes it.'
            : phase === 'finished'
              ? 'A full board. An even match.'
              : moveCount
                ? 'Back to you. Make it count.'
                : 'You go first. Make it count.';

  return (
    <div className="play-layout">
      <div className="play-copy">
        <h2>
          Think you’ve
          <br />
          got <span className="serif">the edge?</span>
        </h2>
        <p>
          One board. Two minds. No second guesses.
          <br />
          Drop your first disc and find out.
        </p>
        <div className="player-key">
          <span>
            <i className="key-disc red" /> YOU / RED
          </span>
          <span>
            <i className="key-disc yellow" /> MACHINE / YELLOW
          </span>
        </div>
        <div className="demo-note">
          <Sparkles size={18} />
          <p>
            A little taste of Pefforza. This browser demo uses its own search
            opponent. Run the Python project for the full solver, neural agent,
            camera, and voice.
          </p>
        </div>
        <a
          href="https://github.com/tzii/Pefforza_4#quick-start"
          target="_blank"
          rel="noreferrer"
          className="text-link"
        >
          Meet the full engine <ArrowUpRight size={16} />
        </a>
      </div>
      <div className="game-shell">
        <div className="game-toolbar">
          <span className="game-live">
            <i className="status-dot" /> THE PLAYGROUND
          </span>
          <Select
            value={difficulty}
            onValueChange={(value) => {
              if (value === 'easy' || value === 'medium' || value === 'hard')
                dispatch({ type: 'reset', difficulty: value });
            }}
          >
            <SelectTrigger
              aria-label="Difficulty; changing it starts a new game"
              className="difficulty-select"
            >
              <SelectValue>
                {difficulty.charAt(0).toUpperCase() + difficulty.slice(1)}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="easy">Easy</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="hard">Hard</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <output className="game-status" aria-live="polite" aria-atomic="true">
          <span className={phase === 'thinking' ? 'thinking-text' : ''}>
            {message}
          </span>
          {phase === 'error' && (
            <button onClick={() => dispatch({ type: 'retry' })}>
              Try again
            </button>
          )}
        </output>
        <fieldset
          className={`game-board ${phase === 'finished' ? 'game-finished' : ''}`}
          style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
          aria-label="Connect Four board"
          aria-describedby="game-instructions"
        >
          <legend className="sr-only">Connect Four board</legend>
          {Array.from({ length: cols }, (_, column) => (
            <button
              type="button"
              data-column={column}
              key={column}
              className="game-column"
              aria-disabled={phase !== 'ready' || board[column] !== empty}
              aria-label={`Drop red disc in column ${column + 1}. ${
                Array.from({ length: rows }, (_, r) => board[r * cols + column])
                  .filter(Boolean)
                  .map((value) => (value === human ? 'red' : 'yellow'))
                  .join(', ') || 'Empty'
              }.`}
              onKeyDown={(event) => {
                if (/^[1-7]$/.test(event.key)) {
                  event.preventDefault();
                  play(Number(event.key) - 1);
                }
              }}
              onClick={() => play(column)}
            >
              <span className="column-pointer" aria-hidden="true">
                <ArrowDown size={16} />
              </span>
              {Array.from({ length: rows }, (_, r) => {
                const index = r * cols + column;
                const value = board[index];
                return (
                  <span
                    key={r}
                    className={`game-cell ${value === human ? 'cell-red' : value === ai ? 'cell-yellow' : ''} ${line.includes(index) ? 'cell-winner' : ''}`}
                  >
                    <span
                      key={`${state.round}-${value}`}
                      className={`disc ${last === index ? 'disc-last' : ''}`}
                      aria-hidden="true"
                    >
                      {value === human ? '×' : value === ai ? '○' : ''}
                    </span>
                  </span>
                );
              })}
              <span className="column-label" aria-hidden="true">
                {column + 1}
              </span>
            </button>
          ))}
        </fieldset>
        <div className="game-bottom">
          <span>
            {String(moveCount).padStart(2, '0')} MOVES{' '}
            <span className="muted">/ {rows * cols}</span>
          </span>
          <button
            className="reset-button"
            onClick={() => dispatch({ type: 'reset' })}
          >
            <RotateCcw size={14} /> New game
          </button>
        </div>
        <p className="game-instructions" id="game-instructions">
          Choose a column. Connect four discs in any direction.
          <br />
          Keyboard: Tab to the board, then use 1–7 or Enter.
        </p>
      </div>
    </div>
  );
}
