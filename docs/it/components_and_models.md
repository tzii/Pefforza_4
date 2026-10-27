# Mappa del Repository, Componenti e Modelli di Dominio

> 🇬🇧 [English version](../components_and_models.md)

Questo modulo descrive l'organizzazione dei file, le classi e le funzioni di
ciascun blocco logico e le strutture dati che modellano il gioco.

---

## 1. Mappa del repository

| Path | Tipo | Ruolo | Note |
|:---|:---|:---|:---|
| `pefforza/` | Cartella | Package Python principale | Tutti i moduli importabili. |
| [pefforza/constants.py](../../pefforza/constants.py) | File | Singola fonte di verità geometrica | `ROWS`, `COLS`, `WIN_LENGTH`, ID giocatori, percorso del modello. |
| [pefforza/rules.py](../../pefforza/rules.py) | File | Logica di gioco pura | Funzioni sul tabellone senza dipendenze pesanti. |
| `pefforza/agent/` | Cartella | Motori decisionali | Livelli, ricerca, addestramento, valutazione. |
| [pefforza/agent/difficulty.py](../../pefforza/agent/difficulty.py) | File | Registro delle difficoltà | Associa i nomi dei livelli alle factory degli agenti. |
| [pefforza/agent/minimax.py](../../pefforza/agent/minimax.py) | File | Baseline negamax a matrice + safety net | Riferimento di correttezza per i motori bitboard. |
| [pefforza/agent/search/](../../pefforza/agent/search/) | Cartella | Motori bitboard | `BitPosition`, alpha-beta del livello `hard`, `PerfectSolver`, `OpeningBook`. |
| [pefforza/agent/oracle.py](../../pefforza/agent/oracle.py) | File | Valutazione con oracolo esatto | Valuta qualsiasi agente mossa per mossa contro i punteggi del solver. |
| `pefforza/agent/data/` | Cartella | Dati inclusi | `opening_book.xz` (533k posizioni), `oracle_positions.json` (729 posizioni). |
| [pefforza/agent/networks.py](../../pefforza/agent/networks.py) | File | Tronco della rete neurale | `Connect4CNN`, un features extractor SB3. |
| [pefforza/agent/train.py](../../pefforza/agent/train.py) | File | Addestramento | Distillazione dal solver e PPO (entrambi i colori, avversario selezionabile). |
| [pefforza/agent/evaluate.py](../../pefforza/agent/evaluate.py) | File | Valutazione headless | Partite tra agenti, oracolo, confronto tra livelli. |
| [pefforza/envs/connect4_env.py](../../pefforza/envs/connect4_env.py) | File | `Connect4Env` Gymnasium | Transizioni di stato, ricompense, azioni legali. |
| [pefforza/interaction/voice.py](../../pefforza/interaction/voice.py) | File | Motore vocale non bloccante | Coda asincrona, backend `pyttsx3` / `NullBackend`. |
| [pefforza/vision/board_detector.py](../../pefforza/vision/board_detector.py) | File | Rilevamento e classificazione | Localizzazione automatica, warp, classificazione HSV adattiva. |
| [pefforza/vision/validation.py](../../pefforza/vision/validation.py) | File | Validazione delle letture | Controlli di gravità, turno, esito e storia. |
| [pefforza/vision/diagnose.py](../../pefforza/vision/diagnose.py) | File | Diagnostica live | Etichette e confidenze per cella sul feed live. |
| [pefforza/cli/](../../pefforza/cli/) | Cartella | Implementazione degli entrypoint | `play_cli`, `play_gui`, `play_physical` (console script). |
| `play_cli.py`, `play_gui.py`, `play_physical.py`, [main.py](../../main.py) | File | Shim nella root | Mantengono `python play_cli.py`; `main.py` = physical `--watch --voice`. |
| [scripts/](../../scripts/) | Cartella | Strumenti offline | Wrapper del solver nativo, generatori di book/oracolo/dati teacher, benchmark. |
| `tests/` | Cartella | Test unitari, comportamentali ed end-to-end | Headless: niente camera, audio o modello addestrato. |
| [pyproject.toml](../../pyproject.toml) | File | Configurazione progetto e strumenti | Metadati, dipendenze, ruff, mypy, pytest, coverage. |

---

## 2. Scomposizione per componente

### `Connect4Env`

* **File**: [pefforza/envs/connect4_env.py](../../pefforza/envs/connect4_env.py)
* **Responsabilità**: ambiente conforme a Gymnasium con `reset()` e `step()`.
* **API**: `Connect4Env(gym.Env)`; `step(action)` gioca una colonna, passa il
  turno, assegna le ricompense e rileva la fine della partita;
  `valid_action_mask()` restituisce le colonne legali.
* **Input / output**: azione intera (0-6) / osservazione (`Board`),
  ricompensa, terminated, truncated, info.
* **Errori**: azioni fuori range o colonne piene restituiscono una penalità
  di `-10.0` e terminano l'episodio.
* **Side effect**: modifica `self.board` e `self.current_player`.

### `BoardDetector` e `locate_board`

* **File**: [pefforza/vision/board_detector.py](../../pefforza/vision/board_detector.py)
* **Responsabilità**: trovare la scacchiera, normalizzare l'immagine e
  classificare le pedine.
* **API**:
  * `locate_board(frame)`: trova i fori non blu racchiusi dal contorno blu,
    adatta il reticolo 6 x 7 ai fori d'angolo, verifica che il reticolo
    preveda i fori rilevati e restituisce i quattro angoli dell'area di
    gioco (oppure `None`).
  * `calibrate(cap, flip, auto=True)`: evidenzia la scacchiera trovata
    (INVIO conferma) oppure accetta quattro angoli cliccati in qualsiasi
    ordine; `set_corners()` calcola il warp.
  * `classify_board_image(img)` / `cell_confidences(img)`: classificazione e
    rapporto di riempimento per cella, con il `ColorProfile` del detector.
  * `adapt_colors(img, grid)`: riadatta le bande di hue rosso/giallo e le
    soglie S/V a una lettura affidabile; il nuovo profilo viene adottato
    solo se riproduce esattamente quella lettura.
  * `physical_col(display_col)`: converte la colonna dello schermo
    specchiato in quella fisica.
* **Note**: le ROI delle celle sono ridotte del 20% (`_CELL_MARGIN_FRAC`) per
  ignorare la plastica; il rosso usa due intervalli di hue perché attraversa
  0/180.

### `BoardStateValidator`

* **File**: [pefforza/vision/validation.py](../../pefforza/vision/validation.py)
* **Responsabilità**: accettare solo letture fisicamente e temporalmente
  plausibili - gravità, conteggi con il rosso che inizia, esito coerente e
  transizione legale (una pedina o un giro completo) dall'ultimo stato
  accettato; una scacchiera svuotata dopo una partita finita avvia una nuova
  partita.

### `PhysicalAssistant` e `StableGridFilter`

* **File**: [pefforza/cli/play_physical.py](../../pefforza/cli/play_physical.py)
* **Responsabilità**: il percorso decisionale dell'assistente AR senza
  camera (validare, riconoscere la fine partita, attendere l'avversario,
  interrogare l'agente) e il filtro di `--watch` che emette una lettura solo
  dopo che è rimasta identica per N frame.

### Motori di ricerca

* **File**: [pefforza/agent/search/](../../pefforza/agent/search/) e
  [pefforza/agent/minimax.py](../../pefforza/agent/minimax.py); dettagli in
  [search_engine.md](../search_engine.md) (in inglese).
* `BitboardSearchAgent`: alpha-beta a profondità 8 con transposition table,
  il livello `hard`, vincolato alla baseline a matrice da test differenziali.
* `PerfectSolver`: solver esatto vittoria/pareggio/sconfitta; `solve_root`
  dimostra le mosse radice a turni alternati entro un budget di tempo.
* `OpeningBook`: mosse fortemente ottimali per ogni posizione che l'IA può
  raggiungere fino al ply 17, indicizzate da chiavi bitboard canoniche per
  simmetria.
* `tactical_safety_net(agent)`: avvolge un agente in modo che prenda sempre
  una vittoria immediata o blocchi una minaccia immediata.

### Livello neurale

* **File**: [networks.py](../../pefforza/agent/networks.py),
  [train.py](../../pefforza/agent/train.py)
* `Connect4CNN` trasforma il tabellone in piani self/avversario/vuoto e
  applica convoluzioni 3 x 3; è il tronco condiviso di una normale policy
  SB3 `PPO`, quindi i checkpoint si caricano con `PPO.load`.
* `distill()` addestra la policy sulla distribuzione delle colonne
  esattamente ottimali e la value head sull'esito della partita, a partire
  da posizioni etichettate dal solver; `SinglePlayerWrapper` + `train()`
  permettono il fine-tuning con PPO.
* Durante il gioco `model_agent` esclude le colonne piene dalla policy.

### `VoiceEngine`

* **File**: [pefforza/interaction/voice.py](../../pefforza/interaction/voice.py)
* **Responsabilità**: sintesi vocale asincrona che non rallenta mai il gioco.
* **API**: `speak(text)` accoda una frase; `play_move_commentary(col,
  confidence)` costruisce un commento alla mossa; `shutdown()` svuota il
  worker.
* **Design**: produttore-consumatore su coda thread-safe. Se `pyttsx3` non si
  inizializza o manca un dispositivo audio, il motore si disattiva
  (fail-soft); `PEFFORZA_TTS_BACKEND=null` forza il backend silenzioso.

---

## 3. Modello dei dati

Non serve un database: i dati vivono in memoria come array NumPy tipizzati,
interi bitboard e dataclass.

### Tabellone (`rules.Board`)

Array NumPy `int8` 6 x 7.

| Cella | Significato | Codifica |
|:---|:---|:---|
| `board[r, c] == 0` | Vuota | `EMPTY` |
| `board[r, c] == 1` | Giocatore 1 | L'agente stesso (vista agente) / rosso (vista visione) |
| `board[r, c] == 2` | Giocatore 2 | L'avversario (vista agente) / giallo (vista visione) |

### `BitPosition`

Sette bit per colonna (sei celle più un bit sentinella). `current` contiene
le pedine di chi muove, `mask` tutte le pedine; `key = current + mask` e
`canonical_key = min(key, chiave specchiata)` indicizzano la transposition
table e l'opening book.

### Posizione dell'oracolo

`OraclePosition(moves, scores, source)`: una sequenza di mosse e il
punteggio esatto di ogni colonna dal punto di vista di chi muove (`0`
pareggio, `s > 0` vittoria con `s` pedine ancora in mano, `s < 0`
sconfitta, `None` colonna piena); `source` è `line` o `random`.

### `RootResult` / `SearchResult`

`RootResult(move, outcome, proven, nodes, elapsed)` descrive la scelta del
solver esatto e se è dimostrata (`win_now`, `proven_win`, `proven_draw`,
`all_lost`) o è il `fallback` allo scadere del tempo.
`SearchResult(column, score, depth, nodes, elapsed)` profila la ricerca
della baseline a matrice.

---

## 4. Indice dei concetti

| Concetto | File | Spiegazione |
|:---|:---|:---|
| **Geometria del gioco** | [constants.py](../../pefforza/constants.py) | Dimensioni del tabellone e codifica delle celle. |
| **Regole e vittorie** | [rules.py](../../pefforza/rules.py) | Allineamenti di 4 orizzontali, verticali e diagonali. |
| **Ambiente RL** | [connect4_env.py](../../pefforza/envs/connect4_env.py) | Stati, azioni e ricompense per Gymnasium. |
| **Gioco perfetto** | [search/perfect.py](../../pefforza/agent/search/perfect.py), [search/book.py](../../pefforza/agent/search/book.py) | Solver esatto e opening book del livello `impossible`. |
| **Misurare la perfezione** | [oracle.py](../../pefforza/agent/oracle.py) | Percentuali di mosse che conservano il valore ed esattamente ottimali per livello. |
| **Raddrizzamento prospettico** | [board_detector.py](../../pefforza/vision/board_detector.py) | Angoli automatici o manuali, warp omografico. |
| **Riconoscimento del colore** | [board_detector.py](../../pefforza/vision/board_detector.py) | Soglie HSV adattive e rapporti di riempimento. |
| **Validazione delle letture** | [validation.py](../../pefforza/vision/validation.py) | Scarta le letture implausibili prima che l'IA le veda. |
| **Coda vocale su thread** | [voice.py](../../pefforza/interaction/voice.py) | Il worker daemon tiene la voce fuori dal thread di gioco. |
