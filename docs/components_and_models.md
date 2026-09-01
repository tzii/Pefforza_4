# Mappa del Repository, Componenti e Modelli di Dominio

Questo modulo descrive nel dettaglio l'organizzazione dei file all'interno del repository, le classi e le funzioni che compongono ciascun blocco logico, e le strutture dati che modellano il dominio del gioco Forza 4.

---

## 1. Mappa del Repository

| Path | Tipo | Ruolo nel progetto | Note |
|:---|:---|:---|:---|
| `pefforza/` | Cartella | Package Python principale | Contiene tutti i moduli core importabili. |
| [pefforza/constants.py](../pefforza/constants.py) | File | Singola fonte di verità geometrica | Definisce dimensioni (`ROWS`, `COLS`, `WIN_LENGTH`) e ID dei giocatori. |
| [pefforza/rules.py](../pefforza/rules.py) | File | Logica pura di gioco | Funzioni pure e matematiche sul tabellone (senza dipendenze pesanti). |
| `pefforza/agent/` | Cartella | Motori decisionali dell'avversario | Contiene addestramento, euristiche, minimax ed esecuzione del modello. |
| [pefforza/agent/difficulty.py](../pefforza/agent/difficulty.py) | File | Registro delle difficoltà dell'IA | Associa le stringhe di difficoltà ai factory degli agenti decisionali. |
| [pefforza/agent/minimax.py](../pefforza/agent/minimax.py) | File | Algoritmo Negamax + Alpha-Beta | Implementa la ricerca euristica ad albero, l'iterative deepening e la safety net. |
| [pefforza/agent/train.py](../pefforza/agent/train.py) | File | Script di addestramento PPO | Configura l'ambiente in modalità self-play/random e allena con SB3. |
| [pefforza/agent/evaluate.py](../pefforza/agent/evaluate.py) | File | Harness di valutazione headless | Esegue simulazioni batch tra agenti per valutarne la win-rate. |
| `pefforza/envs/` | Cartella | Ambiente di simulazione Gymnasium | Contiene la definizione dell'ambiente RL. |
| [pefforza/envs/connect4_env.py](../pefforza/envs/connect4_env.py) | File | Ambiente Gymnasium Connect4Env | Gestisce transizioni di stato, ricompense ed azioni legali. |
| `pefforza/interaction/` | Cartella | Modulo di interazione audio/TTS | Gestisce i feedback sonori del sistema. |
| [pefforza/interaction/voice.py](../pefforza/interaction/voice.py) | File | Motore vocale non bloccante | Implementa la coda asincrona e i backend `pyttsx3` / `NullBackend`. |
| `pefforza/vision/` | Cartella | Pipeline di computer vision | Gestisce l'elaborazione dei flussi video. |
| [pefforza/vision/board_detector.py](../pefforza/vision/board_detector.py) | File | Rilevatore e calibratore visivo | Esegue il warp prospettico e la classificazione dei colori. |
| [pefforza/vision/diagnose.py](../pefforza/vision/diagnose.py) | File | Utility live di diagnostica | Mostra un feed interattivo con le confidenze per cella. |
| [play_cli.py](../play_cli.py) | File | Entrypoint terminale | Permette di avviare il gioco direttamente da CLI. |
| [play_gui.py](../play_gui.py) | File | Entrypoint GUI | Gioco interattivo 2D basato su Pygame con watchdog abilitato. |
| [play_physical.py](../play_physical.py) | File | Entrypoint AR on-demand | L'IA suggerisce le mosse premendo la barra spaziatrice. |
| [main.py](../main.py) | File | Entrypoint AR real-time continuo | Analizza continuamente la telecamera ed annuncia le mosse automaticamente. |
| `tests/` | Cartella | Unit e Behavioral test | Contiene la suite completa dei test automatizzati eseguiti da pytest. |
| [pyproject.toml](../pyproject.toml) | File | Configurazione progetto e build | Dichiara metadati, dipendenze esterne e impostazioni di linting. |

---

## 2. Component-by-Component Breakdown

### Component: `Connect4Env`
*   **File**: [pefforza/envs/connect4_env.py](../pefforza/envs/connect4_env.py)
*   **Responsabilità**: Implementare l'ambiente di addestramento conforme allo standard Gymnasium di OpenAI, esponendo le funzioni `reset()` e `step()`.
*   **Funzioni/classi principali**:
    *   `Connect4Env(gym.Env)`: Classe principale dell'ambiente.
    *   `step(action: int)`: Esegue una mossa nella colonna selezionata. Gestisce la transizione di turno, l'assegnazione dei punteggi e il controllo di fine partita.
    *   `valid_action_mask()`: Ritorna un array booleano indicante le mosse legali (colonne non piene).
*   **Input**: Azione intera (colonna da 0 a 6).
*   **Output**: Nuova osservazione (`Board`), ricompensa (float), terminated (bool), truncated (bool), info (dict).
*   **Dipendenze**: [pefforza/rules.py](../pefforza/rules.py), `gymnasium`, `numpy`.
*   **Errori gestiti**: Tentativi di mosse fuori dal range (0-6) o su colonne sature ritornano una penalità severa di `-10.0` e terminano l'episodio di addestramento.
*   **Side effect**: Modifica lo stato interno di `self.board` e inverte `self.current_player`.

### Component: `BoardDetector`
*   **File**: [pefforza/vision/board_detector.py](../pefforza/vision/board_detector.py)
*   **Responsabilità**: Rilevamento visivo della scacchiera, normalizzazione dell'immagine e classificazione del colore dei token inseriti.
*   **Funzioni/classi principali**:
    *   `calibrate(cap, flip)`: Esegue l'acquisizione manuale dei quattro punti d'angolo e calcola la matrice omografica di warping.
    *   `classify_board_image(board_img)`: Scansiona una scacchiera raddrizzata ritagliando le ROI (*Region Of Interest*) delle celle e classificandole.
    *   `cell_confidences(board_img)`: Calcola la percentuale di pixel colorati per cella rispetto alla soglia, restituendo un array bidimensionale di confidenza.
*   **Input**: Frame video BGR (`np.ndarray`).
*   **Output**: Griglia di interi `(6, 7)` con codifica $0, 1, 2$ e frame OpenCV deformato.
*   **Dipendenze**: `cv2` (OpenCV), `numpy`.
*   **Note tecniche**: La calibrazione richiede un ordine preciso dei punti (**TL -> TR -> BR -> BL**). Le ROI delle celle sono rimpicciolite tramite un inset del 20% (`_CELL_MARGIN_FRAC = 0.20`) per eliminare il rumore delle griglie di plastica della scacchiera.

### Component: `MinimaxAgent`
*   **File**: [pefforza/agent/minimax.py](../pefforza/agent/minimax.py)
*   **Responsabilità**: Agente minimax euristico ad alta precisione con potatura alfa-beta e limitazione temporale adattiva.
*   **Funzioni/classi principali**:
    *   `search(board, my_id, depth)`: Esegue una ricerca Negamax completa a profondità fissa.
    *   `search_with_time_budget(board, my_id, time_budget, ...)`: Ricerca ad approfondimento iterativo (*Iterative Deepening*). Profonda l'albero ply per ply finché non esaurisce il tempo a disposizione.
    *   `tactical_safety_net(agent)`: Decoratore che forza l'agente a giocare una mossa vincente immediata o a bloccare una minaccia avversaria immediata (1-ply lookahead).
*   **Input**: Griglia di gioco, ID dell'agente, colonne valide.
*   **Output**: Mossa finale raccomandata (intero $0-6$).
*   **Dipendenze**: [pefforza/rules.py](../pefforza/rules.py).
*   **Note tecniche**: Per massimizzare le prestazioni, la scacchiera viene mutata sul posto (*in-place*) durante la ricorsione e ripristinata nel backtrack, eliminando l'overhead di allocazione in memoria. L'ordinamento delle mosse predefinito è centrale (`[3, 2, 4, 1, 5, 0, 6]`), il che velocizza drasticamente la potatura dei rami (tagli alfa-beta).

### Component: `VoiceEngine`
*   **File**: [pefforza/interaction/voice.py](../pefforza/interaction/voice.py)
*   **Responsabilità**: Gestione asincrona del Text-to-Speech senza rallentare il thread grafico o di elaborazione principale.
*   **Funzioni/classi principali**:
    *   `VoiceEngine`: Manager che istanzia la coda e avvia il thread daemon lavoratore.
    *   `speak(text)`: Accoda una stringa di testo per la riproduzione vocale.
    *   `play_move_commentary(col, confidence)`: Genera un commento vocale specifico in base alla colonna giocata e alla confidenza della mossa.
*   **Input**: Stringa di testo.
*   **Output**: Output audio hardware.
*   **Dipendenze**: `pyttsx3`, `threading`, `queue`.
*   **Design pattern**: Implementa una struttura produttore-consumatore basata su coda thread-safe. Se il backend `pyttsx3` fallisce l'inizializzazione o non è presente hardware audio, si attiva automaticamente il `NullBackend`, rendendo il sistema "fail-soft" ed evitando crash di gioco.

---

## 3. Domain Model / Data Model

Il progetto non necessita di database relazionali complessi. I dati sono strutturati principalmente in memoria attraverso array NumPy fortemente tipizzati e dataclass Python.

### Scacchiera (`rules.Board`)
Rappresentata come un array bidimensionale NumPy di tipo `np.int8` con dimensioni $6 \times 7$.

| Riga/Colonna | Significato | Codifica |
|:---|:---|:---|
| `board[r, c] == 0` | Cella vuota | `EMPTY` |
| `board[r, c] == 1` | Pedina Giocatore 1 | `AI_PLAYER` (nella prospettiva del modello) / Rosso (nella visione) |
| `board[r, c] == 2` | Pedina Giocatore 2 | `HUMAN_PLAYER` (nella prospettiva del modello) / Giallo (nella visione) |

### Dataclass: `SearchResult`
Definita in [pefforza/agent/minimax.py](../pefforza/agent/minimax.py) per profilare le prestazioni della ricerca euristica.

| Campo | Tipo | Significato |
|:---|:---|:---|
| `column` | `int` | Colonna ottimale trovata dal motore di ricerca. |
| `score` | `int` | Punteggio euristico stimato della mossa (depth-discounted). |
| `depth` | `int` | Profondità massima raggiunta nell'albero delle mosse. |
| `nodes` | `int` | Numero totale di nodi dell'albero di ricerca valutati. |
| `elapsed` | `float` | Tempo impiegato per la ricerca in secondi. |

---

## 4. File-to-Concept Index

| Concetto | Files | Spiegazione |
|:---|:---|:---|
| **Geometria del Gioco** | [constants.py](../pefforza/constants.py) | Definisce le costanti fisiche e le convenzioni numeriche per le celle vuote, rosse e gialle. |
| **Regole e Vittorie** | [rules.py](../pefforza/rules.py) | Contiene gli algoritmi per verificare la presenza di allineamenti orizzontali, verticali e diagonali di 4 pedine. |
| **Ambiente di Reinforcement Learning** | [connect4_env.py](../pefforza/envs/connect4_env.py) | Fornisce la rappresentazione del gioco sotto forma di stati, azioni e ricompense per Gymnasium. |
| **Ricerca Alfa-Beta** | [minimax.py](../pefforza/agent/minimax.py) | Contiene il nucleo algoritmico Negamax per il calcolo delle varianti di gioco ad albero profondo. |
| **Raddrizzamento Prospettico** | [board_detector.py](../pefforza/vision/board_detector.py) | Esegue la calibrazione geometrica manuale e corregge la prospettiva sghemba del feed webcam. |
| **Riconoscimento Colore** | [board_detector.py](../pefforza/vision/board_detector.py) | Converte le immagini in coordinate HSV ed applica filtri di soglia per identificare la presenza dei token rosso/giallo. |
| **Threaded Speech Queue** | [voice.py](../pefforza/interaction/voice.py) | Gestisce il ciclo del thread daemon per evitare che la riproduzione vocale interrompa la fluidità grafica. |
