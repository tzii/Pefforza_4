import { AudioLines, BrainCircuit, ScanLine } from 'lucide-react';
import { cols, rows, newBoard, drop, human, ai } from '@/lib/game';

const moves = [3, 2, 3, 4, 2, 4, 1, 5, 3, 3, 2, 5];
const example = moves.reduce(
  (board, col, i) => drop(board, col, i % 2 ? ai : human) ?? board,
  newBoard(),
);

function BoardDiagram({ mode }: { mode: 'scan' | 'ar' }) {
  return (
    <div className={`diagram-board ${mode}`}>
      <div
        className="diagram-grid"
        style={{ gridTemplateColumns: `repeat(${cols},1fr)` }}
        aria-hidden="true"
      >
        {example.map((value, i) => (
          <span
            key={i}
            className={`diagram-cell ${value === human ? 'red' : value === ai ? 'yellow' : ''}`}
          >
            {mode === 'scan' && (
              <small>{value ? (value === human ? 'R' : 'Y') : '+'}</small>
            )}
          </span>
        ))}
      </div>
      {mode === 'scan' ? (
        <>
          <div className="scan-line" />
          <i className="corner tl" />
          <i className="corner tr" />
          <i className="corner bl" />
          <i className="corner br" />
          <span className="scan-tag">BOARD DETECTED</span>
          <span className="scan-dim">
            {cols} × {rows} / HSV CLASSIFICATION
          </span>
        </>
      ) : (
        <>
          <span className="ar-arrow">↓</span>
          <span className="ar-column">COLUMN 04</span>
        </>
      )}
    </div>
  );
}

export function Story() {
  return (
    <section
      className="story"
      id="how-it-works"
      aria-label="How Pefforza sees, thinks, and plays"
    >
      <div className="story-stage">
        <div className="story-heading">
          <span>THE ANATOMY OF A MOVE</span>
          <span className="story-drag-hint">
            KEEP SCROLLING <span>→</span>
          </span>
          <div className="story-progress">
            <span />
          </div>
        </div>
        <div className="story-track">
          <article className="story-panel panel-see">
            <div className="story-copy">
              <span className="chapter-kicker">
                <ScanLine size={17} /> 01 / PERCEPTION
              </span>
              <h2>
                First,
                <br />
                it <span className="serif">sees.</span>
              </h2>
              <p>
                Your board. Your table. One webcam.
                <br />
                Computer vision finds the grid and reads every red and yellow
                disc. The real world becomes a game state.
              </p>
              <div className="chapter-detail">
                <span>THE EYES</span>
                <span>
                  OpenCV · HSV classification
                  <br />
                  Four-point calibration
                </span>
              </div>
            </div>
            <div className="story-visual vision-visual">
              <div className="visual-topline">
                <span>
                  <i /> COMPUTER VISION
                </span>
                <span>ILLUSTRATIVE VIEW</span>
              </div>
              <BoardDiagram mode="scan" />
              <div className="vision-readout">
                <span>
                  INPUT <b>REAL-WORLD BOARD</b>
                </span>
                <span className="readout-arrow">→</span>
                <span>
                  OUTPUT <b>A DIGITAL POSITION</b>
                </span>
              </div>
            </div>
            <span className="chapter-giant" aria-hidden="true">
              01
            </span>
          </article>
          <article className="story-panel panel-think">
            <div className="story-copy">
              <span className="chapter-kicker">
                <BrainCircuit size={17} /> 02 / INTELLIGENCE
              </span>
              <h2>
                Then,
                <br />
                it <span className="serif">thinks.</span>
              </h2>
              <p>
                Every move opens a new possibility.
                <br />
                Pefforza searches ahead, spots threats, and chooses its reply.
                Five difficulty modes. Five very different minds.
              </p>
              <div className="chapter-detail">
                <span>THE BRAIN</span>
                <span>
                  Bitboard alpha-beta search
                  <br />
                  Exact solver · PPO neural policy
                </span>
              </div>
            </div>
            <div className="story-visual search-visual">
              <div className="visual-topline">
                <span>
                  <i /> EXPLORING POSSIBILITIES
                </span>
                <span>SEARCH CONCEPT</span>
              </div>
              <svg
                className="search-tree"
                viewBox="0 0 540 380"
                aria-hidden="true"
              >
                <g fill="none" stroke="#697456" strokeWidth="1.3">
                  <path d="M270 60L90 165M270 60L270 165M270 60L450 165M90 165L35 280M90 165L90 280M90 165L145 280M270 165L210 280M270 165L270 280M270 165L330 280M450 165L395 280M450 165L450 280M450 165L505 280" />
                </g>
                <path
                  className="search-path"
                  d="M270 60L270 165L330 280"
                  fill="none"
                  stroke="#d5fa35"
                  strokeWidth="3"
                />
                <g fill="#182013" stroke="#687753" strokeWidth="1.3">
                  {[
                    [270, 60],
                    [90, 165],
                    [450, 165],
                    [35, 280],
                    [90, 280],
                    [145, 280],
                    [210, 280],
                    [270, 280],
                    [395, 280],
                    [450, 280],
                    [505, 280],
                  ].map(([cx, cy]) => (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={cy === 60 ? 23 : cy === 165 ? 16 : 10}
                      key={`${cx}-${cy}`}
                    />
                  ))}
                </g>
                <circle cx="270" cy="165" r="16" fill="#d5fa35" />
                <circle cx="330" cy="280" r="13" fill="#d5fa35" />
                <text
                  x="270"
                  y="66"
                  fill="#d5fa35"
                  textAnchor="middle"
                  fontSize="16"
                >
                  ?
                </text>
                <text
                  x="330"
                  y="324"
                  fill="#d5fa35"
                  textAnchor="middle"
                  fontSize="12"
                  letterSpacing="2"
                >
                  THE NEXT MOVE
                </text>
              </svg>
              <div className="engine-tags">
                <span>RANDOM</span>
                <span>HEURISTIC</span>
                <span>MINIMAX</span>
                <span>EXACT</span>
                <span>NEURAL</span>
              </div>
            </div>
            <span className="chapter-giant" aria-hidden="true">
              02
            </span>
          </article>
          <article className="story-panel panel-play">
            <div className="story-copy">
              <span className="chapter-kicker">
                <AudioLines size={17} /> 03 / INTERACTION
              </span>
              <h2>
                And the
                <br />
                game <span className="serif">talks.</span>
              </h2>
              <p>
                A move you can see. A reply you can hear.
                <br />
                An augmented-reality arrow points the way, while optional voice
                commentary keeps the conversation going.
              </p>
              <div className="chapter-detail">
                <span>THE CONNECTION</span>
                <span>
                  AR guidance · Voice commentary
                  <br />
                  Terminal · Desktop · Physical board
                </span>
              </div>
            </div>
            <div className="story-visual interaction-visual">
              <div className="visual-topline">
                <span>
                  <i /> HUMAN × MACHINE
                </span>
                <span>EXAMPLE OUTPUT</span>
              </div>
              <BoardDiagram mode="ar" />
              <div className="voice-bubble">
                <div className="waveform" aria-hidden="true">
                  {[12, 21, 34, 17, 27, 40, 24, 14, 30, 20, 10].map((h, i) => (
                    <i
                      key={i}
                      style={{ height: h, animationDelay: `${i * 0.09}s` }}
                    />
                  ))}
                </div>
                <span>“I’d play column four.”</span>
                <AudioLines size={18} />
              </div>
            </div>
            <span className="chapter-giant" aria-hidden="true">
              03
            </span>
          </article>
        </div>
      </div>
    </section>
  );
}
