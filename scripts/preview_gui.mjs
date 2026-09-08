// Python owns the game. This view only lays out state and interpolates a drop.
export class DropTimeline {
  constructor() { this.drop = null; this.startedAt = 0; }
  sync(drop, receivedAt, transitMs = 0) {
    if (!drop) { this.drop = null; return; }
    if (!this.drop || this.drop.id !== drop.id) {
      this.startedAt = receivedAt - drop.elapsed - Math.max(0, transitMs);
    }
    this.drop = drop;
  }
  progress(now, reducedMotion = false) {
    if (!this.drop) return null;
    if (reducedMotion) return 1;
    return Math.min(1, Math.max(0, (now - this.startedAt) / this.drop.duration));
  }
}

if (typeof document !== 'undefined') {
  const $ = id => document.getElementById(id);
  const token = document.querySelector('meta[name="preview-token"]').content;
  const game = $('game');
  const namespace = 'http://www.w3.org/2000/svg';
  const colors = {1:'#f98478', 2:'#efcd6f'};
  const timeline = new DropTimeline();
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let state = null, connected = false, boardKey = '', animationFrame = null;
  let pieces, moving, highlight, columnButtons = [], lastHover = null;
  let commandQueue = Promise.resolve();

  function svg(tag, attributes, parent) {
    const element = document.createElementNS(namespace, tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (parent) parent.append(element);
    return element;
  }
  function text(id, value) {
    if ($(id).textContent !== value) $(id).textContent = value;
  }
  function piece(player, parent) {
    const group = svg('g', {}, parent);
    svg('circle', {r:29, fill:colors[player], stroke:'#111622', 'stroke-width':1}, group);
    svg('circle', {r:19, fill:'none', stroke:'#111622', 'stroke-opacity':.28, 'stroke-width':2}, group);
    const glyph = svg('text', {x:0, y:5, 'text-anchor':'middle', fill:'#111622', 'font-size':16}, group);
    glyph.textContent = player === 1 ? 'X' : 'O';
    return group;
  }
  function buildBoard(snapshot) {
    const width = snapshot.columns * 80, height = snapshot.rows * 80;
    game.setAttribute('viewBox', `-16 -40 ${width + 32} ${height + 60}`);
    svg('rect', {x:-16, y:-12, width:width+32, height:height+32, rx:28, fill:'#090d17'}, game);
    svg('rect', {x:-16, y:-16, width:width+32, height:height+32, rx:28, fill:'#263048', stroke:'#3d4a64'}, game);
    highlight = svg('rect', {y:0, width:70, height, rx:24, fill:'#2e3f52'}, game);
    for (let row=0; row<snapshot.rows; row++) {
      for (let col=0; col<snapshot.columns; col++) {
        svg('circle', {cx:col*80+40, cy:row*80+40, r:32, class:'slot'}, game);
      }
    }
    pieces = svg('g', {id:'pieces'}, game);
    moving = svg('g', {id:'moving-piece'}, game);
    const nav = document.querySelector('.column-controls');
    nav.style.gridTemplateColumns = `repeat(${snapshot.columns}, 1fr)`;
    for (let col=0; col<snapshot.columns; col++) {
      const button = document.createElement('button');
      button.textContent = col + 1;
      button.setAttribute('aria-label', `Drop in column ${col+1}`);
      button.addEventListener('click', () => send({kind:'key', key:String(col+1)}));
      nav.append(button);
      columnButtons.push(button);
    }
  }
  function canPlay() {
    return connected && state && state.player === 1 && !state.gameOver &&
      !state.animation && !state.lessonAttempted;
  }
  function select(column) {
    const active = canPlay() && state.board[0][column] === 0;
    highlight.setAttribute('visibility', active ? 'visible' : 'hidden');
    highlight.setAttribute('x', column*80+5);
    columnButtons.forEach((button, col) => {
      button.disabled = !canPlay() || state.board[0][col] !== 0;
      button.classList.toggle('selected', active && col === column);
    });
  }
  function drawDrop(now) {
    animationFrame = null;
    const progress = timeline.progress(now, reducedMotion.matches);
    if (progress === null) { moving.replaceChildren(); return; }
    const drop = timeline.drop;
    const y = -28 + ((drop.row*80+40) + 28) * progress**2;
    moving.setAttribute('transform', `translate(${drop.column*80+40} ${y})`);
    if (progress < 1) animationFrame = requestAnimationFrame(drawDrop);
  }
  function render(snapshot, receivedAt, transitMs) {
    state = snapshot;
    if (!pieces) buildBoard(state);
    const key = JSON.stringify([state.board, state.winningCells]);
    if (key !== boardKey) {
      pieces.replaceChildren();
      for (let row=0; row<state.rows; row++) {
        for (let col=0; col<state.columns; col++) {
          if (state.board[row][col]) {
            const token = piece(state.board[row][col], pieces);
            token.setAttribute('transform', `translate(${col*80+40} ${row*80+40})`);
          }
        }
      }
      for (const [row,col] of state.winningCells) {
        svg('circle', {cx:col*80+40, cy:row*80+40, r:35, class:'winning'}, pieces);
      }
      text('board', state.board.map(row => row.map(p => p===1?'X':p===2?'O':'.').join(' ')).join('\n'));
      boardKey = key;
    }
    const previousDrop = timeline.drop;
    timeline.sync(state.animation, receivedAt, transitMs);
    if (!state.animation || !previousDrop || previousDrop.id !== state.animation.id) {
      moving.replaceChildren();
      if (state.animation) piece(state.animation.player, moving);
    }
    if (animationFrame === null) drawDrop(performance.now());
    select(state.selectedColumn);
    const lesson = state.lesson !== null;
    text('headline', lesson ? 'Tiny tactics.' : 'Four in a row.');
    text('subtitle', lesson ? state.lessonTitle : 'One more round?');
    text('counter', lesson ? `Lesson ${state.lesson+1} / ${state.lessonCount}` : `Move ${String(state.moves + Number(!state.gameOver)).padStart(2,'0')}`);
    let turn = state.player === 1 ? 'Your turn' : 'Thinking…';
    if (state.gameOver) turn = state.winner===1 ? 'You got four!' : state.winner===2 ? 'AI got four.' : 'A worthy draw.';
    if (lesson) turn = state.lessonSolved ? 'You found it!' : state.lessonAttempted ? 'Try again' : 'Your challenge';
    if (state.animation) turn = state.animation.player===1 ? 'Nice drop.' : "AI’s move";
    text('turn', turn);
    text('status', state.status);
    $('status').dataset.moves = state.moves;
    $('status').dataset.gameOver = state.gameOver;
    text('opponent-heading', lesson ? 'Keep exploring' : 'Your opponent');
    text('difficulty', lesson ? 'Next lesson' : state.difficulty);
    text('difficulty-key', lesson ? 'N / next' : 'D / new round');
    text('opponent-copy', lesson ? 'One move, one idea. Retry freely; hints explain the answer.' : state.opponentCopy);
    text('restart-label', lesson ? 'Try again' : state.gameOver ? 'Play again' : 'New round');
    text('lessons-label', lesson ? 'Free play' : 'Tactical lessons');
    document.querySelector('[data-key="u"]').disabled = !lesson && state.moves===0 && !state.animation;
    document.querySelector('[data-key="h"]').disabled = Boolean(state.animation) || (!lesson && (state.gameOver || state.player!==1));
  }
  function disconnect() {
    connected = false;
    timeline.sync(null, performance.now());
    if (moving) moving.replaceChildren();
    if (state) select(state.selectedColumn);
    document.querySelectorAll('[data-key]').forEach(button => { button.disabled = true; });
    text('connection', 'Disconnected · reconnecting…');
  }
  function send(payload) {
    if (!connected) return;
    // Serialize controls so fast Undo / Restart cannot overtake an earlier drop.
    commandQueue = commandQueue.then(async () => {
      const response = await fetch('/event', {
        method:'POST', headers:{'Content-Type':'application/json','X-Preview-Token':token},
        body:JSON.stringify(payload), signal:AbortSignal.timeout(3000)
      });
      if (response.status === 403) {
        // A restarted local server creates a fresh session token.
        location.reload();
        return;
      }
      if (!response.ok) throw new Error('Input rejected');
    }).catch(disconnect);
  }
  document.querySelectorAll('[data-key]').forEach(button => {
    button.addEventListener('click', () => send({kind:'key',key:button.dataset.key}));
  });
  document.addEventListener('keydown', event => {
    if (event.target.closest('button') && ['Enter',' '].includes(event.key)) return;
    const key = event.key.length===1 ? event.key.toLowerCase() : event.key;
    if (['1','2','3','4','5','6','7','r','u','h','d','l','n','ArrowLeft','ArrowRight','Enter',' '].includes(key)) {
      event.preventDefault();
      if (!event.repeat) send({kind:'key',key});
    }
  });
  function pointerColumn(event) {
    if (!state) return null;
    const point = new DOMPoint(event.clientX,event.clientY).matrixTransform(game.getScreenCTM().inverse());
    const col = Math.floor(point.x/80);
    return col>=0 && col<state.columns && point.y>=-40 && point.y<state.rows*80 ? col : null;
  }
  game.addEventListener('click', event => {
    const column = pointerColumn(event);
    if (column !== null && canPlay()) send({kind:'key',key:String(column+1)});
  });
  game.addEventListener('pointermove', event => {
    const column = pointerColumn(event);
    if (column !== null && canPlay() && column !== lastHover) {
      lastHover = column;
      select(column);
      send({kind:'select',column});
    }
  });
  game.addEventListener('pointerleave', () => { lastHover = null; });
  reducedMotion.addEventListener('change', () => {
    if (timeline.drop && animationFrame === null) drawDrop(performance.now());
  });
  async function refresh() {
    const sentAt = performance.now();
    try {
      const response = await fetch('/state', {cache:'no-store',signal:AbortSignal.timeout(3000)});
      if (!response.ok) throw new Error('Preview unavailable');
      const snapshot = await response.json();
      const receivedAt = performance.now();
      connected = true;
      document.querySelectorAll('[data-key]').forEach(button => { button.disabled = false; });
      render(snapshot, receivedAt, (receivedAt-sentAt)/2);
      text('connection', 'Local game · one shared round');
    } catch { disconnect(); }
    // Network cadence does not set animation cadence: RAF draws between updates.
    setTimeout(refresh, document.hidden ? 250 : connected ? 32 : 500);
  }
  refresh();
}
